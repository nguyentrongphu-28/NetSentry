"""SQLite implementation of SessionRepository."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.domain.entities.user import Role, User
from app.domain.interfaces.session_repository import SessionRepository
from app.repositories.database import connect


def _parse_iso(val: str | None) -> datetime | None:
    if not val:
        return None
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteSessionRepository(SessionRepository):
    """SQLite-backed session token storage."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        return connect(self._db_path)

    def create(
        self,
        token_hash: str,
        user_id: int,
        created_at: datetime,
        expires_at: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        ua_trunc = user_agent[:200] if user_agent else None
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        token_hash, user_id, created_at, last_seen_at,
                        expires_at, client_ip, user_agent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        token_hash,
                        user_id,
                        created_at.isoformat(),
                        created_at.isoformat(),
                        expires_at.isoformat(),
                        client_ip,
                        ua_trunc,
                    ),
                )
        finally:
            conn.close()

    def get_valid(
        self,
        token_hash: str,
        now: datetime,
        idle_minutes: int,
    ) -> tuple[User, datetime] | None:
        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT s.token_hash, s.last_seen_at, s.expires_at,
                       u.id AS user_id, u.username, u.role, u.is_active,
                       u.must_change_password, u.created_at AS user_created_at,
                       u.last_login_at
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()

            if not row:
                return None

            if not bool(row["is_active"]):
                return None

            expires_at = _parse_iso(row["expires_at"])
            last_seen_at = _parse_iso(row["last_seen_at"])
            if not expires_at or not last_seen_at:
                return None

            # Absolute expiration check
            if now > expires_at:
                return None

            # Idle expiration check
            idle_delta = (now - last_seen_at).total_seconds()
            if idle_delta > (idle_minutes * 60):
                return None

            user = User(
                id=row["user_id"],
                username=row["username"],
                role=Role(row["role"]),
                is_active=True,
                must_change_password=bool(row["must_change_password"]),
                created_at=_parse_iso(row["user_created_at"]) or datetime.now(timezone.utc),
                last_login_at=_parse_iso(row["last_login_at"]),
            )
            return user, last_seen_at
        finally:
            conn.close()

    def touch(self, token_hash: str, now: datetime) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
                    (now.isoformat(), token_hash),
                )
        finally:
            conn.close()

    def delete(self, token_hash: str) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        finally:
            conn.close()

    def delete_all_for_user(
        self,
        user_id: int,
        except_token_hash: str | None = None,
    ) -> int:
        conn = self._get_connection()
        try:
            with conn:
                if except_token_hash:
                    cursor = conn.execute(
                        "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
                        (user_id, except_token_hash),
                    )
                else:
                    cursor = conn.execute(
                        "DELETE FROM sessions WHERE user_id = ?",
                        (user_id,),
                    )
                return cursor.rowcount
        finally:
            conn.close()

    def purge_expired(self, now: datetime) -> int:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM sessions WHERE expires_at <= ?",
                    (now.isoformat(),),
                )
                return cursor.rowcount
        finally:
            conn.close()
