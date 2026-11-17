"""Core dependencies, providers and authentication verification."""

from __future__ import annotations

from dataclasses import dataclass
import secrets

from app.core.config import Settings
from app.services.audit_run_service import AuditRunService
from app.services.device_service import DeviceService


def verify_api_key(
    provided_key: str | None,
    expected_key: str | None,
    *,
    auth_disabled: bool = False,
) -> bool:
    """Verify API key using constant-time comparison.

    Returns True if auth_disabled is True.
    Returns False if either key is missing.
    Never logs or raises with key contents.
    """
    if auth_disabled:
        return True
    if not provided_key or not expected_key:
        return False
    return secrets.compare_digest(provided_key, expected_key)


@dataclass(frozen=True, slots=True)
class AppDependencies:
    """Dependency container for application services and configuration."""

    settings: Settings
    device_service: DeviceService
    audit_run_service: AuditRunService
