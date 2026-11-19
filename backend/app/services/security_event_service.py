"""Security event logging service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.domain.entities.security_event import SecurityEvent, SecurityEventType
from app.domain.interfaces.security_event_repository import SecurityEventRepository


class SecurityEventService:
    """Domain service for recording and retrieving security audit events."""

    def __init__(
        self,
        event_repo: SecurityEventRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._event_repo = event_repo
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        dt = self._clock()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def record(
        self,
        event_type: SecurityEventType,
        actor_username: str | None = None,
        client_ip: str | None = None,
        target: str | None = None,
        detail: str | None = None,
    ) -> SecurityEvent:
        """Record a security event. Ensures secrets are never stored."""
        return self._event_repo.add(
            occurred_at=self._now(),
            event_type=event_type,
            actor_username=actor_username,
            client_ip=client_ip,
            target=target,
            detail=detail,
        )

    def list_events(
        self,
        limit: int = 50,
        before_id: int | None = None,
        event_type: SecurityEventType | None = None,
    ) -> list[SecurityEvent]:
        """List security events."""
        return self._event_repo.list(limit=limit, before_id=before_id, event_type=event_type)

    def purge_old_events(self, max_days: int = 90, max_rows: int = 10000) -> int:
        """Purge old security events on startup."""
        return self._event_repo.purge(max_days=max_days, max_rows=max_rows)
