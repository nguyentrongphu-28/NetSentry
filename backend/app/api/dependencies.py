"""FastAPI dependencies for NetSentry API."""

from __future__ import annotations

from fastapi import Depends, Request

from app.api.deps import (
    Principal,
    get_audit_run_service,
    get_auth_service,
    get_current_principal,
    get_device_service,
    get_remediation_service,
    get_security_event_service,
    get_session_repository,
    get_settings,
    get_user_service,
    require_role,
    resolve_principal,
)
from app.core.config import Settings
from app.core.dependencies import verify_api_key
from app.domain.entities.user import Role
from app.domain.errors import NotAuthenticatedError

# Keep UnauthorizedError for backwards compatibility with any existing tests
UnauthorizedError = NotAuthenticatedError


def require_api_key(
    request: Request,
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
) -> None:
    """Backwards compatibility shim requiring an authenticated principal."""
    pass
