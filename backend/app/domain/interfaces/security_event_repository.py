"""Abstract interface for security event repository."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.security_event import SecurityEvent, SecurityEventType


class SecurityEventRepository(ABC):
    """Abstract contract for security audit event logging."""

    @abstractmethod
    def add(
        self,
        occurred_at: datetime,
        event_type: SecurityEventType,
        actor_username: str | None = None,
        client_ip: str | None = None,
        target: str | None = None,
        detail: str | None = None,
    ) -> SecurityEvent:
        """Record a new security event."""
        raise NotImplementedError

    @abstractmethod
    def list(
        self,
        limit: int = 50,
        before_id: int | None = None,
        event_type: SecurityEventType | None = None,
    ) -> list[SecurityEvent]:
        """List security events sorted by occurred_at DESC, id DESC with pagination."""
        raise NotImplementedError

    @abstractmethod
    def purge(self, max_days: int = 90, max_rows: int = 10000) -> int:
        """Purge events older than max_days or keep at most max_rows newest events."""
        raise NotImplementedError
