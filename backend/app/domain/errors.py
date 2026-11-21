"""Domain-level error definitions for NetSentry."""

from __future__ import annotations


class NetSentryError(Exception):
    """Base exception for all domain and connector errors in NetSentry."""

    code: str = "NETSENTRY_ERROR"

    def __init__(self, message: str, *, host: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.host = host

    def __str__(self) -> str:
        return self.message


class AuthenticationFailedError(NetSentryError):
    """Raised when SSH authentication fails."""

    code: str = "AUTH_FAILED"

class InvalidCurrentPasswordError(NetSentryError):
    code = "INVALID_CURRENT_PASSWORD"

class ConnectionTimeoutError(NetSentryError):
    """Raised when connection or command execution times out."""

    code: str = "CONNECT_TIMEOUT"


class ConnectionFailedError(NetSentryError):
    """Raised when SSH connection cannot be established or drops unexpectedly."""

    code: str = "CONNECT_FAILED"


class CommandNotAllowedError(NetSentryError):
    """Raised when a requested command is not in the allowed command list."""

    code: str = "COMMAND_NOT_ALLOWED"


class ConfigCollectionError(NetSentryError):
    """Raised when configuration retrieval fails (e.g. invalid privilege mode or IOS command error)."""

    code: str = "COLLECTION_FAILED"


class UnsupportedPlatformError(NetSentryError):
    """Raised when a connector is requested for an unsupported device platform."""

    code: str = "UNSUPPORTED_PLATFORM"


# ---------------------------------------------------------------------------
# Persistence & API layer errors (added in persistence/API phase)
# ---------------------------------------------------------------------------

class DeviceNotFoundError(NetSentryError):
    """Raised when a requested device does not exist in the repository."""

    code: str = "DEVICE_NOT_FOUND"


class DuplicateDeviceError(NetSentryError):
    """Raised when adding a device whose device_id or (host, port) already exists."""

    code: str = "DEVICE_EXISTS"


class InvalidDeviceError(NetSentryError):
    """Raised when device creation parameters fail validation."""

    code: str = "INVALID_DEVICE"


class AuditNotFoundError(NetSentryError):
    """Raised when a requested audit run does not exist in the repository."""

    code: str = "AUDIT_NOT_FOUND"


class AuditAlreadyRunningError(NetSentryError):
    """Raised when an audit is already in progress for the given device."""

    code: str = "AUDIT_ALREADY_RUNNING"


class CredentialsRequiredError(NetSentryError):
    """Raised when no credentials are available to perform an audit."""

    code: str = "CREDENTIALS_REQUIRED"


# ---------------------------------------------------------------------------
# Auth, RBAC & Public Mode errors (added in auth-rbac phase)
# ---------------------------------------------------------------------------

class InvalidCredentialsError(NetSentryError):
    """Raised when username or password authentication fails."""

    code: str = "INVALID_CREDENTIALS"


class AccountLockedError(NetSentryError):
    """Raised when an account is temporarily locked due to too many failed attempts."""

    code: str = "ACCOUNT_LOCKED"


class RateLimitedError(NetSentryError):
    """Raised when request rate limit is exceeded."""

    code: str = "RATE_LIMITED"

    def __init__(self, message: str = "Too many requests", *, retry_after: int = 300) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NotAuthenticatedError(NetSentryError):
    """Raised when request lacks authentication."""

    code: str = "UNAUTHORIZED"


class ForbiddenError(NetSentryError):
    """Raised when authenticated principal lacks required role/permission."""

    code: str = "FORBIDDEN"


class PasswordChangeRequiredError(NetSentryError):
    """Raised when user must change password before performing other actions."""

    code: str = "PASSWORD_CHANGE_REQUIRED"


class WeakPasswordError(NetSentryError):
    """Raised when password fails strength validation policy."""

    code: str = "WEAK_PASSWORD"


class UserExistsError(NetSentryError):
    """Raised when creating a user with an already existing username."""

    code: str = "USER_EXISTS"


class UserNotFoundError(NetSentryError):
    """Raised when a user is not found."""

    code: str = "USER_NOT_FOUND"


class LastAdminError(NetSentryError):
    """Raised when attempting to deactivate or demote the last active admin."""

    code: str = "LAST_ADMIN"


class OriginNotAllowedError(NetSentryError):
    """Raised when request Origin or Referer header fails CSRF validation."""

    code: str = "ORIGIN_NOT_ALLOWED"


class BodyCredentialsDisabledError(NetSentryError):
    """Raised when credentials are provided in request body but server forbids it (e.g. public mode)."""

    code: str = "BODY_CREDENTIALS_DISABLED"
