"""SQLite implementation of SecurityEventRepository."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.domain.entities.security_event import SecurityEvent, SecurityEventType
from app.domain.interfaces.security_event_repository import SecurityEventRepository
from app.repositories.database import connect


def _parse_iso(val: str | None) -> datetime:
    if not val:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteSecurityEventRepository(SecurityEventRepository):
    """SQLite-backed security event log."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        return connect(self._db_path)

    def add(
        self,
        occurred_at: datetime,
        event_type: SecurityEventType,
        actor_username: str | None = None,
        client_ip: str | None = None,
        target: str | None = None,
        detail: str | None = None,
    ) -> SecurityEvent:
        detail_trunc = detail[:200] if detail else None
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO security_events (
                        occurred_at, event_type, actor_username,
                        client_ip, target, detail
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        occurred_at.isoformat(),
                        event_type.value,
                        actor_username,
                        client_ip,
                        target,
                        detail_trunc,
                    ),
                )
                event_id = cursor.lastrowid
                assert event_id is not None
        finally:
            conn.close()

        return SecurityEvent(
            id=event_id,
            occurred_at=occurred_at,
            event_type=event_type,
            actor_username=actor_username,
            client_ip=client_ip,
            target=target,
            detail=detail_trunc,
        )

    def list(
        self,
        limit: int = 50,
        before_id: int | None = None,
        event_type: SecurityEventType | None = None,
    ) -> list[SecurityEvent]:
        safe_limit = min(max(1, limit), 200)
        query = ["SELECT id, occurred_at, event_type, actor_username, client_ip, target, detail FROM security_events WHERE 1=1"]
        params: list[object] = []

        if before_id is not None:
            query.append("AND id < ?")
            params.append(before_id)

        if event_type is not None:
            query.append("AND event_type = ?")
            params.append(event_type.value)

        query.append("ORDER BY id DESC LIMIT ?")
        params.append(safe_limit)

        sql = " ".join(query)
        conn = self._get_connection()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [
                SecurityEvent(
                    id=row["id"],
                    occurred_at=_parse_iso(row["occurred_at"]),
                    event_type=SecurityEventType(row["event_type"]),
                    actor_username=row["actor_username"],
                    client_ip=row["client_ip"],
                    target=row["target"],
                    detail=row["detail"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def purge(self, max_days: int = 90, max_rows: int = 10000) -> int:
        now_ts = datetime.now(timezone.utc).timestamp()
        cutoff_iso = datetime.fromtimestamp(now_ts - (max_days * 86400), tz=timezone.utc).isoformat()

        conn = self._get_connection()
        try:
            with conn:
                # 1. Purge events older than max_days
                cur1 = conn.execute("DELETE FROM security_events WHERE occurred_at < ?", (cutoff_iso,))
                deleted = cur1.rowcount

                # 2. Keep at most max_rows newest events
                cur2 = conn.execute(
                    """
                    DELETE FROM security_events WHERE id NOT IN (
                        SELECT id FROM security_events ORDER BY id DESC LIMIT ?
                    )
                    """,
                    (max_rows,),
                )
                deleted += cur2.rowcount
                return deleted
        finally:
            conn.close()
