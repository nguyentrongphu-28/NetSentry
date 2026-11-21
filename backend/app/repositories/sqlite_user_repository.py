"""SQLite implementation of UserRepository."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.domain.entities.user import Role, User, UserWithHash
from app.domain.errors import UserExistsError, UserNotFoundError
from app.domain.interfaces.user_repository import UserRepository
from app.repositories.database import connect


def _parse_iso(val: str | None) -> datetime | None:
    if not val:
        return None
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SQLiteUserRepository(UserRepository):
    """SQLite-backed user storage."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        return connect(self._db_path)

    def add(
        self,
        username: str,
        password_hash: str,
        role: Role,
        must_change_password: bool = True,
    ) -> User:
        norm_username = username.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        must_change_int = 1 if must_change_password else 0

        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users (
                        username, password_hash, role, is_active,
                        must_change_password, failed_attempts, created_at
                    ) VALUES (?, ?, ?, 1, ?, 0, ?)
                    """,
                    (norm_username, password_hash, role.value, must_change_int, now_iso),
                )
                user_id = cursor.lastrowid
                assert user_id is not None
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: users.username" in str(e):
                raise UserExistsError(f"User '{username}' already exists.") from e
            raise
        finally:
            conn.close()

        return User(
            id=user_id,
            username=norm_username,
            role=role,
            is_active=True,
            must_change_password=must_change_password,
            created_at=_parse_iso(now_iso) or datetime.now(timezone.utc),
            last_login_at=None,
        )

    def get_by_id(self, user_id: int) -> User | None:
        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT id, username, role, is_active, must_change_password, created_at, last_login_at
                FROM users WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
            if not row:
                return None
            return User(
                id=row["id"],
                username=row["username"],
                role=Role(row["role"]),
                is_active=bool(row["is_active"]),
                must_change_password=bool(row["must_change_password"]),
                created_at=_parse_iso(row["created_at"]) or datetime.now(timezone.utc),
                last_login_at=_parse_iso(row["last_login_at"]),
            )
        finally:
            conn.close()

    def get_by_username(self, username: str) -> UserWithHash | None:
        norm_username = username.strip().lower()
        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT id, username, password_hash, role, is_active,
                       must_change_password, failed_attempts, locked_until,
                       created_at, last_login_at
                FROM users WHERE username = ?
                """,
                (norm_username,),
            ).fetchone()
            if not row:
                return None
            return UserWithHash(
                id=row["id"],
                username=row["username"],
                password_hash=row["password_hash"],
                role=Role(row["role"]),
                is_active=bool(row["is_active"]),
                must_change_password=bool(row["must_change_password"]),
                failed_attempts=int(row["failed_attempts"]),
                locked_until=_parse_iso(row["locked_until"]),
                created_at=_parse_iso(row["created_at"]) or datetime.now(timezone.utc),
                last_login_at=_parse_iso(row["last_login_at"]),
            )
        finally:
            conn.close()

    def list(self) -> list[User]:
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, username, role, is_active, must_change_password, created_at, last_login_at
                FROM users ORDER BY id ASC
                """
            ).fetchall()
            return [
                User(
                    id=row["id"],
                    username=row["username"],
                    role=Role(row["role"]),
                    is_active=bool(row["is_active"]),
                    must_change_password=bool(row["must_change_password"]),
                    created_at=_parse_iso(row["created_at"]) or datetime.now(timezone.utc),
                    last_login_at=_parse_iso(row["last_login_at"]),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def update_role_active(
        self,
        user_id: int,
        role: Role | None = None,
        is_active: bool | None = None,
    ) -> User:
        conn = self._get_connection()
        try:
            with conn:
                row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
                if not row:
                    raise UserNotFoundError(f"User with ID {user_id} not found.")

                updates: list[str] = []
                params: list[object] = []

                if role is not None:
                    updates.append("role = ?")
                    params.append(role.value)
                if is_active is not None:
                    updates.append("is_active = ?")
                    params.append(1 if is_active else 0)

                if updates:
                    params.append(user_id)
                    conn.execute(
                        f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                        tuple(params),
                    )
        finally:
            conn.close()

        updated_user = self.get_by_id(user_id)
        assert updated_user is not None
        return updated_user

    def update_password(
        self,
        user_id: int,
        password_hash: str,
        must_change_password: bool = False,
    ) -> None:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE users
                    SET password_hash = ?, must_change_password = ?
                    WHERE id = ?
                    """,
                    (password_hash, 1 if must_change_password else 0, user_id),
                )
                if cursor.rowcount == 0:
                    raise UserNotFoundError(f"User with ID {user_id} not found.")
        finally:
            conn.close()

    def record_login_success(self, user_id: int, at: datetime) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE users
                    SET failed_attempts = 0, locked_until = NULL, last_login_at = ?
                    WHERE id = ?
                    """,
                    (at.isoformat(), user_id),
                )
        finally:
            conn.close()

    def register_failed_attempt(
        self,
        user_id: int,
        at: datetime,
        max_attempts: int,
        lock_minutes: int,
    ) -> tuple[int, datetime | None]:
        conn = self._get_connection()
        try:
            with conn:
                row = conn.execute(
                    "SELECT failed_attempts, locked_until FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if not row:
                    raise UserNotFoundError(f"User with ID {user_id} not found.")

                previous = int(row["failed_attempts"])
                if row["locked_until"]:
                    prev_lock = datetime.fromisoformat(row["locked_until"])
                    if prev_lock.tzinfo is None:
                        prev_lock = prev_lock.replace(tzinfo=timezone.utc)
                    if prev_lock <= at:
                        previous = 0  # lock expired: start a fresh counting window

                new_count = previous + 1
                locked_until: datetime | None = None
                locked_until_iso: str | None = None

                if new_count >= max_attempts:
                    locked_until = datetime.fromtimestamp(
                        at.timestamp() + (lock_minutes * 60),
                        tz=timezone.utc,
                    )
                    locked_until_iso = locked_until.isoformat()

                conn.execute(
                    """
                    UPDATE users
                    SET failed_attempts = ?, locked_until = ?
                    WHERE id = ?
                    """,
                    (new_count, locked_until_iso, user_id),
                )
                return new_count, locked_until
        finally:
            conn.close()

    def count_active_admins(self) -> int:
        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) as count FROM users
                WHERE role = 'admin' AND is_active = 1
                """
            ).fetchone()
            return int(row["count"]) if row else 0
        finally:
            conn.close()
