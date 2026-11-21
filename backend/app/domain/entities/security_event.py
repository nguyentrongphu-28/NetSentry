"""Security event domain entities for NetSentry audit logging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SecurityEventType(str, Enum):
    """Types of security-relevant events tracked in NetSentry."""

    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGIN_LOCKED = "LOGIN_LOCKED"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET = "PASSWORD_RESET"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    DEVICE_CREATED = "DEVICE_CREATED"
    DEVICE_DELETED = "DEVICE_DELETED"
    AUDIT_STARTED = "AUDIT_STARTED"
    ACCESS_DENIED = "ACCESS_DENIED"
    SNAPSHOT_VIEWED = "SNAPSHOT_VIEWED"
    SNAPSHOT_DELETED = "SNAPSHOT_DELETED"
    AI_EXPLAIN_REQUESTED = "AI_EXPLAIN_REQUESTED"


@dataclass(frozen=True)
class SecurityEvent:
    """Security audit log record."""

    id: int
    occurred_at: datetime
    event_type: SecurityEventType
    actor_username: str | None
    client_ip: str | None
    target: str | None
    detail: str | None
