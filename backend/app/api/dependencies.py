"""FastAPI dependencies for NetSentry API."""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader

from app.core.config import Settings
from app.core.dependencies import verify_api_key
from app.services.audit_run_service import AuditRunService
from app.services.device_service import DeviceService

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class UnauthorizedError(Exception):
    """Raised when an API key is missing or invalid."""


def require_api_key(
    request: Request,
    api_key: str | None = Depends(api_key_header),
) -> None:
    settings: Settings = request.app.state.settings
    if not verify_api_key(api_key, settings.api_key, auth_disabled=settings.auth_disabled):
        raise UnauthorizedError("Invalid or missing API key")


def get_device_service(request: Request) -> DeviceService:
    return request.app.state.device_service


def get_audit_run_service(request: Request) -> AuditRunService:
    return request.app.state.audit_run_service


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
