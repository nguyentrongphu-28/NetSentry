"""Application factory for NetSentry REST API."""

from __future__ import annotations

import logging
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import audits, devices, health
from app.core.config import Settings
from app.factories.connector_factory import ConnectorFactory, build_default_connector_factory
from app.repositories.audit_repository import SqliteAuditRepository
from app.repositories.database import init_db
from app.repositories.device_repository import SqliteDeviceRepository
from app.rules.registry import build_default_engine
from app.services.audit_run_service import AuditRunService
from app.services.audit_service import AuditService
from app.services.device_service import DeviceService

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
    audit_run_service = AuditRunService(
        device_repository=device_repo,
        audit_repository=audit_repo,
        audit_service=audit_core_service,
        default_credentials=lambda: app_settings.default_credentials,
    )

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

    # Attach services to state for dependency injection
    app.state.settings = app_settings
    app.state.device_service = device_service
    app.state.audit_run_service = audit_run_service

    # Configure CORS
    if app_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(app_settings.cors_origins),
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["X-API-Key", "Content-Type"],
            allow_credentials=False,
        )

    # Register error handlers
    register_exception_handlers(app)

    # Register routes
    app.include_router(health.router)

    api_v1_router = APIRouter(prefix="/api/v1")
    api_v1_router.include_router(devices.router)
    api_v1_router.include_router(audits.router)
    app.include_router(api_v1_router)

    return app
