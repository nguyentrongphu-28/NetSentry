"""Application factory for NetSentry REST API."""

from __future__ import annotations

import logging
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.middleware import OriginCheckMiddleware, SecurityHeadersMiddleware
from app.api.routes import ai, audits, auth, baselines, compare, devices, health, remediation, security_events, snapshots, users
from app.core.config import Settings
from app.clients.ollama_client import OllamaClient
from app.factories.connector_factory import ConnectorFactory, build_default_connector_factory
from app.repositories.audit_repository import SqliteAuditRepository
from app.repositories.database import connect, init_db
from app.repositories.device_repository import SqliteDeviceRepository
from app.repositories.file_snapshot_store import FileSnapshotStore
from app.repositories.sqlite_ai_explanation_repository import SqliteAiExplanationRepository
from app.repositories.sqlite_baseline_repository import SqliteBaselineRepository
from app.repositories.sqlite_drift_repository import SqliteDriftRepository
from app.repositories.sqlite_remediation_repository import SqliteRemediationRepository
from app.repositories.sqlite_security_event_repository import SQLiteSecurityEventRepository
from app.repositories.sqlite_session_repository import SQLiteSessionRepository
from app.repositories.sqlite_snapshot_repository import SqliteSnapshotRepository
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.rules.registry import build_default_engine
from app.security.password_hasher import Argon2PasswordHasher
from app.security.rate_limiter import InMemorySlidingWindowLimiter
from app.services.ai_explain_service import AiExplainService
from app.services.audit_run_service import AuditRunService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.baseline_service import BaselineService
from app.services.device_service import DeviceService
from app.services.diff_service import DiffService
from app.services.drift_service import DriftService
from app.services.remediation_service import RemediationService
from app.services.security_event_service import SecurityEventService
from app.services.snapshot_service import SnapshotService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    connector_factory: ConnectorFactory | None = None,
) -> FastAPI:
    """Create and configure a new NetSentry FastAPI application instance."""
    app_settings = settings if settings is not None else Settings.from_env()

    if app_settings.auth_disabled:
        logger.warning(
            "NETSENTRY_AUTH_DISABLED is enabled! API authentication is completely disabled."
        )

    # Initialise persistence
    init_db(app_settings.db_path)

    device_repo = SqliteDeviceRepository(app_settings.db_path)
    audit_repo = SqliteAuditRepository(app_settings.db_path)
    user_repo = SQLiteUserRepository(app_settings.db_path)
    session_repo = SQLiteSessionRepository(app_settings.db_path)
    event_repo = SQLiteSecurityEventRepository(app_settings.db_path)

    # In public mode, refuse startup if no active admin user exists
    if app_settings.public_mode:
        active_admins = user_repo.count_active_admins()
        if active_admins == 0:
            raise RuntimeError(
                "NETSENTRY_PUBLIC_MODE=1 requires at least one active admin user in the database. "
                "Run 'python backend/scripts/create_admin.py --username <admin>' first."
            )

    # Build services
    conn_factory = (
        connector_factory
        if connector_factory is not None
        else build_default_connector_factory()
    )
    engine = build_default_engine()
    audit_core_service = AuditService(connector_factory=conn_factory, engine=engine)

    device_service = DeviceService(
        device_repo,
        allowed_networks=app_settings.allowed_networks,
    )

    # Snapshot infrastructure
    snapshot_dir = app_settings.snapshot_dir or (app_settings.db_path.parent / "snapshots")
    file_store = FileSnapshotStore(snapshot_dir)
    snapshot_repo = SqliteSnapshotRepository(app_settings.db_path)
    # Purge orphan snapshot files at startup
    known_files = snapshot_repo.list_all_file_names()
    file_store.cleanup_orphans(known_files)

    from app.security.config_redactor import ConfigRedactor
    from app.security.config_normalizer import ConfigNormalizer
    hmac_key = app_settings.snapshot_hmac_key or "netsentry-snapshot-default-key"
    redactor = ConfigRedactor(hmac_key=hmac_key)

    baseline_repo = SqliteBaselineRepository(app_settings.db_path)
    drift_repo = SqliteDriftRepository(app_settings.db_path)

    snapshot_service = SnapshotService(
        snapshot_repository=snapshot_repo,
        file_store=file_store,
        redactor=redactor,
        normalizer=ConfigNormalizer,
        baseline_repository=baseline_repo,
        enabled=app_settings.snapshot_enabled,
        keep=app_settings.snapshot_keep,
        content_api_enabled=app_settings.snapshot_content_api,
    )

    diff_service = DiffService()
    drift_service = DriftService(max_blocks=app_settings.drift_max_blocks)

    baseline_service = BaselineService(
        baseline_repository=baseline_repo,
        drift_repository=drift_repo,
        snapshot_service=snapshot_service,
        drift_service=drift_service,
        audit_run_repository=audit_repo,
        enabled=app_settings.baseline_enabled,
    )

    audit_run_service = AuditRunService(
        device_repository=device_repo,
        audit_repository=audit_repo,
        audit_service=audit_core_service,
        default_credentials=lambda: app_settings.default_credentials,
        snapshot_service=snapshot_service,
        baseline_service=baseline_service,
    )

    # AI infrastructure
    ai_repo = SqliteAiExplanationRepository(app_settings.db_path)
    ollama_client = OllamaClient(
        base_url=app_settings.ollama_url,
        model_name=app_settings.ollama_model,
        allow_remote=app_settings.ollama_allow_remote,
    )
    ai_explain_service = AiExplainService(
        explanation_repository=ai_repo,
        audit_run_service=audit_run_service,
        llm_client=ollama_client,
        enabled=app_settings.ai_enabled,
        timeout_seconds=app_settings.ai_timeout_seconds,
        max_concurrency=app_settings.ai_max_concurrency,
        rate_limit=app_settings.ai_rate_limit,
    )

    password_hasher = Argon2PasswordHasher()
    # Parse login rate limit (e.g. "10/300")
    rate_limit_parts = app_settings.login_rate_limit.split("/")
    max_reqs = int(rate_limit_parts[0]) if len(rate_limit_parts) >= 1 else 10
    window_secs = int(rate_limit_parts[1]) if len(rate_limit_parts) >= 2 else 300
    login_limiter = InMemorySlidingWindowLimiter(max_requests=max_reqs, window_seconds=window_secs)

    event_service = SecurityEventService(event_repo=event_repo)
    # Purge old events at startup
    event_service.purge_old_events()

    auth_service = AuthService(
        user_repo=user_repo,
        session_repo=session_repo,
        event_repo=event_repo,
        password_hasher=password_hasher,
        rate_limiter=login_limiter,
        max_failed_logins=app_settings.max_failed_logins,
        lockout_minutes=app_settings.lockout_minutes,
        session_ttl_minutes=app_settings.session_ttl_minutes,
    )
    user_service = UserService(
        user_repo=user_repo,
        session_repo=session_repo,
        event_repo=event_repo,
        password_hasher=password_hasher,
    )

    remediation_repo = SqliteRemediationRepository(app_settings.db_path)
    remediation_service = RemediationService(
        remediation_repo=remediation_repo,
        device_repo=device_repo,
        audit_repo=audit_repo,
        auth_service=auth_service,
        security_event_repo=event_repo,
        enabled=app_settings.remediation_enabled,
        proposal_ttl_minutes=app_settings.remediation_proposal_ttl_minutes,
        approval_ttl_minutes=app_settings.remediation_approval_ttl_minutes,
        max_audit_age_minutes=app_settings.remediation_max_audit_age_minutes,
        require_distinct_approver=app_settings.remediation_require_distinct_approver,
    )
    remediation_service.scan_and_expire_stale_plans()

    # FastAPI instance
    docs_url = "/docs" if app_settings.enable_docs else None
    redoc_url = "/redoc" if app_settings.enable_docs else None
    openapi_url = "/openapi.json" if app_settings.enable_docs else None

    app = FastAPI(
        title="NetSentry API",
        description="Network Configuration Auditing Platform REST API",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Attach services and repositories to state for dependency injection
    app.state.settings = app_settings
    app.state.device_service = device_service
    app.state.audit_run_service = audit_run_service
    app.state.snapshot_service = snapshot_service
    app.state.diff_service = diff_service
    app.state.drift_service = drift_service
    app.state.baseline_service = baseline_service
    app.state.ai_explain_service = ai_explain_service
    app.state.user_service = user_service
    app.state.auth_service = auth_service
    app.state.remediation_service = remediation_service
    app.state.security_event_service = event_service
    app.state.session_repository = session_repo

    # Add Security Headers & Origin Check Middleware
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(OriginCheckMiddleware, cors_origins=app_settings.cors_origins)

    # Configure CORS
    if app_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(app_settings.cors_origins),
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["X-API-Key", "Content-Type"],
            allow_credentials=False,
        )

    # Register error handlers
    register_exception_handlers(app)

    # Register routes
    app.include_router(health.router)

    api_v1_router = APIRouter(prefix="/api/v1")
    api_v1_router.include_router(auth.router)
    api_v1_router.include_router(devices.router)
    api_v1_router.include_router(audits.router)
    api_v1_router.include_router(snapshots.router)
    api_v1_router.include_router(compare.router)
    api_v1_router.include_router(baselines.router)
    api_v1_router.include_router(ai.router)
    api_v1_router.include_router(users.router)
    api_v1_router.include_router(security_events.router)
    api_v1_router.include_router(remediation.router)
    app.include_router(api_v1_router)

    # Mount SPA static files if enabled
    if app_settings.serve_frontend:
        from app.api.static import mount_static_spa
        mount_static_spa(app, app_settings.frontend_dist)

    return app
