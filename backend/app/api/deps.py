"""Authentication and authorization dependencies for FastAPI endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Literal
from fastapi import Depends, Request
from fastapi.security import APIKeyHeader

from app.core.config import Settings
from app.core.dependencies import verify_api_key
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role, User
from app.domain.errors import (
    ForbiddenError,
    NotAuthenticatedError,
    PasswordChangeRequiredError,
)
from app.domain.interfaces.session_repository import SessionRepository
from app.security.client_ip import resolve_client_ip
from app.security.tokens import hash_token
from app.services.audit_run_service import AuditRunService
from app.services.auth_service import AuthService
from app.services.device_service import DeviceService
from app.services.security_event_service import SecurityEventService
from app.services.user_service import UserService

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class Principal:
    """Authenticated entity (user session, api-key admin, or dev-disabled mock)."""

    user: User | None
    kind: Literal["session", "api_key", "disabled"]
    raw_token: str | None = None

    @property
    def username(self) -> str:
        if self.user:
            return self.user.username
        if self.kind == "api_key":
            return "api-key"
        return "dev-admin"

    @property
    def role(self) -> Role:
        if self.user:
            return self.user.role
        # API key and disabled auth principals have admin privileges
        return Role.ADMIN


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_device_service(request: Request) -> DeviceService:
    return request.app.state.device_service


def get_audit_run_service(request: Request) -> AuditRunService:
    return request.app.state.audit_run_service


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_user_service(request: Request) -> UserService:
    return request.app.state.user_service


def get_security_event_service(request: Request) -> SecurityEventService:
    return request.app.state.security_event_service


def get_session_repository(request: Request) -> SessionRepository:
    return request.app.state.session_repository


def get_client_ip(request: Request) -> str:
    settings = get_settings(request)
    peer_host = request.client.host if request.client else None
    trusted_header_val = None
    if settings.trusted_ip_header:
        trusted_header_val = request.headers.get(settings.trusted_ip_header)
    return resolve_client_ip(
        peer_host=peer_host,
        header_value=trusted_header_val,
        trusted_header_configured=settings.trusted_ip_header,
    )


async def resolve_principal(
    request: Request,
    api_key: str | None = Depends(api_key_header),
) -> Principal | None:
    """Resolve authenticated principal from session cookie or API key."""
    settings = get_settings(request)

    # 1. Dev auth_disabled mode (only when NOT in public mode)
    if settings.auth_disabled and not settings.public_mode:
        dummy_admin = User(
            id=0,
            username="dev-admin",
            role=Role.ADMIN,
            is_active=True,
            must_change_password=False,
            created_at=datetime.now(timezone.utc),
            last_login_at=None,
        )
        return Principal(user=dummy_admin, kind="disabled")

    # 2. Session cookie authentication
    session_cookie = request.cookies.get("netsentry_session")
    if session_cookie:
        session_repo: SessionRepository = get_session_repository(request)
        token_digest = hash_token(session_cookie)
        now = datetime.now(timezone.utc)
        valid = session_repo.get_valid(
            token_hash=token_digest,
            now=now,
            idle_minutes=settings.session_idle_minutes,
        )
        if valid:
            user, _ = valid
            # Touch session
            session_repo.touch(token_digest, now)
            return Principal(user=user, kind="session", raw_token=session_cookie)

    # 3. API Key authentication (only when allowed and not public mode)
    if settings.api_key_auth and not settings.public_mode and api_key:
        if verify_api_key(api_key, settings.api_key, auth_disabled=False):
            return Principal(user=None, kind="api_key")

    return None


async def get_current_principal(
    principal: Principal | None = Depends(resolve_principal),
) -> Principal:
    """Ensure a valid principal exists; raise 401 NotAuthenticatedError otherwise."""
    if not principal:
        raise NotAuthenticatedError("Authentication required")
    return principal


def require_role(*roles: Role) -> Callable[..., Principal]:
    """Dependency factory checking that current principal has one of the allowed roles.

    Enforces:
    - 401 if unauthenticated.
    - 403 PASSWORD_CHANGE_REQUIRED if user must change password (unless route is exempt).
    - 403 FORBIDDEN + records ACCESS_DENIED security event if principal lacks role.
    """

    async def _role_checker(
        request: Request,
        principal: Principal = Depends(get_current_principal),
        event_svc: SecurityEventService = Depends(get_security_event_service),
    ) -> Principal:
        # Check mandatory password change
        path = request.url.path
        is_password_exempt = path.endswith("/auth/me") or path.endswith("/auth/change-password") or path.endswith("/auth/logout")

        if principal.user and principal.user.must_change_password and not is_password_exempt:
            raise PasswordChangeRequiredError("Password change is required before proceeding")

        # Check role permission
        if roles and principal.role not in roles:
            client_ip = get_client_ip(request)
            event_svc.record(
                event_type=SecurityEventType.ACCESS_DENIED,
                actor_username=principal.username,
                client_ip=client_ip,
                target=path,
                detail=f"Forbidden: role '{principal.role.value}' attempted access",
            )
            raise ForbiddenError(f"User role '{principal.role.value}' does not have permission")

        return principal

    return _role_checker
