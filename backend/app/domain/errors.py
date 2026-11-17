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
