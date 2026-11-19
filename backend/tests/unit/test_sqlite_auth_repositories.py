"""Unit tests for SQLite Auth Repositories (Section 9.2)."""

import os
from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.domain.errors import UserExistsError, UserNotFoundError
from app.repositories.database import init_db
from app.repositories.sqlite_security_event_repository import SQLiteSecurityEventRepository
from app.repositories.sqlite_session_repository import SQLiteSessionRepository
from app.repositories.sqlite_user_repository import SQLiteUserRepository


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_auth.db"
    init_db(db_file)
    return db_file


class TestSQLiteUserRepository:
    def test_add_and_get_user(self, test_db_path: Path) -> None:
        repo = SQLiteUserRepository(test_db_path)
        user = repo.add(
            username="Alice",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
            role=Role.ADMIN,
            must_change_password=True,
        )

        assert user.username == "alice"  # normalized to lowercase
        assert user.role == Role.ADMIN
        assert user.is_active is True
        assert user.must_change_password is True

        user_by_id = repo.get_by_id(user.id)
        assert user_by_id is not None
        assert user_by_id.username == "alice"

        user_with_hash = repo.get_by_username("ALICE")
        assert user_with_hash is not None
        assert user_with_hash.password_hash == "$argon2id$v=19$m=65536,t=3,p=4$fakehash"
        assert user_with_hash.to_user() == user_by_id

    def test_add_duplicate_username_raises_user_exists_error(self, test_db_path: Path) -> None:
        repo = SQLiteUserRepository(test_db_path)
        repo.add("bob", "hash1", Role.OPERATOR)
        with pytest.raises(UserExistsError):
            repo.add("BOB", "hash2", Role.VIEWER)

    def test_sql_injection_in_username_is_safe(self, test_db_path: Path) -> None:
        repo = SQLiteUserRepository(test_db_path)
        malicious = "alice'; DROP TABLE users;--"
        repo.add(malicious, "hash", Role.VIEWER)

        fetched = repo.get_by_username(malicious)
        assert fetched is not None
        assert fetched.username == malicious.lower()
        # Ensure users table is intact
        assert len(repo.list()) >= 1

    def test_count_active_admins(self, test_db_path: Path) -> None:
        repo = SQLiteUserRepository(test_db_path)
        assert repo.count_active_admins() == 0

        u1 = repo.add("admin1", "h1", Role.ADMIN)
        u2 = repo.add("admin2", "h2", Role.ADMIN)
        repo.add("operator1", "h3", Role.OPERATOR)
        assert repo.count_active_admins() == 2

        # Deactivate admin2
        repo.update_role_active(u2.id, is_active=False)
        assert repo.count_active_admins() == 1

        # Demote admin1
        repo.update_role_active(u1.id, role=Role.OPERATOR)
        assert repo.count_active_admins() == 0

    def test_register_failed_attempt_and_lockout(self, test_db_path: Path) -> None:
        repo = SQLiteUserRepository(test_db_path)
        u = repo.add("charlie", "h", Role.VIEWER)
        t0 = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)

        count, locked = repo.register_failed_attempt(u.id, t0, max_attempts=3, lock_minutes=15)
        assert count == 1
        assert locked is None

        count, locked = repo.register_failed_attempt(u.id, t0, max_attempts=3, lock_minutes=15)
        assert count == 2
        assert locked is None

        count, locked = repo.register_failed_attempt(u.id, t0, max_attempts=3, lock_minutes=15)
        assert count == 3
        assert locked is not None
        assert locked.timestamp() == t0.timestamp() + (15 * 60)

        # Login success resets counter
        repo.record_login_success(u.id, t0)
        u_fresh = repo.get_by_username("charlie")
        assert u_fresh is not None
        assert u_fresh.failed_attempts == 0
        assert u_fresh.locked_until is None


class TestSQLiteSessionRepository:
    def test_create_and_validate_session(self, test_db_path: Path) -> None:
        user_repo = SQLiteUserRepository(test_db_path)
        user = user_repo.add("alice", "hash", Role.ADMIN)

        sess_repo = SQLiteSessionRepository(test_db_path)
        now = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)
        expires = datetime(2026, 11, 18, 20, 0, 0, tzinfo=timezone.utc)
        token_hash = "token_hash_abc_123"

        sess_repo.create(
            token_hash=token_hash,
            user_id=user.id,
            created_at=now,
            expires_at=expires,
            client_ip="127.0.0.1",
            user_agent="Mozilla/5.0 Test",
        )

        valid_res = sess_repo.get_valid(token_hash, now=now, idle_minutes=30)
        assert valid_res is not None
        sess_user, last_seen = valid_res
        assert sess_user.username == "alice"

        # Exceeded idle timeout
        later_idle = datetime(2026, 11, 18, 12, 35, 0, tzinfo=timezone.utc)
        assert sess_repo.get_valid(token_hash, now=later_idle, idle_minutes=30) is None

        # Touch session and check again
        sess_repo.touch(token_hash, now=datetime(2026, 11, 18, 12, 20, 0, tzinfo=timezone.utc))
        valid_res = sess_repo.get_valid(token_hash, now=later_idle, idle_minutes=30)
        assert valid_res is not None

        # Exceeded absolute expiration
        way_later = datetime(2026, 11, 18, 21, 0, 0, tzinfo=timezone.utc)
        assert sess_repo.get_valid(token_hash, now=way_later, idle_minutes=30) is None

    def test_delete_and_cascade(self, test_db_path: Path) -> None:
        user_repo = SQLiteUserRepository(test_db_path)
        user = user_repo.add("bob", "hash", Role.VIEWER)

        sess_repo = SQLiteSessionRepository(test_db_path)
        now = datetime.now(timezone.utc)
        expires = datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc)

        sess_repo.create("hash_1", user.id, now, expires)
        sess_repo.create("hash_2", user.id, now, expires)

        # Delete all except hash_1
        sess_repo.delete_all_for_user(user.id, except_token_hash="hash_1")
        assert sess_repo.get_valid("hash_1", now, idle_minutes=60) is not None
        assert sess_repo.get_valid("hash_2", now, idle_minutes=60) is None

        # Purge expired
        purged = sess_repo.purge_expired(now=datetime.fromtimestamp(now.timestamp() + 4000, tz=timezone.utc))
        assert purged >= 1


class TestSQLiteSecurityEventRepository:
    def test_add_and_list_events(self, test_db_path: Path) -> None:
        repo = SQLiteSecurityEventRepository(test_db_path)
        now = datetime.now(timezone.utc)

        ev1 = repo.add(
            occurred_at=now,
            event_type=SecurityEventType.LOGIN_SUCCESS,
            actor_username="alice",
            client_ip="127.0.0.1",
            target="device_1",
            detail="User logged in successfully",
        )
        assert ev1.id is not None
        assert ev1.event_type == SecurityEventType.LOGIN_SUCCESS

        events = repo.list(limit=10)
        assert len(events) >= 1
        assert events[0].actor_username == "alice"

        filtered = repo.list(event_type=SecurityEventType.LOGIN_FAILED)
        assert len(filtered) == 0


def test_posix_chmod_0600(tmp_path: Path) -> None:
    db_file = tmp_path / "chmod_test.db"
    init_db(db_file)
    if os.name == "posix":
        mode = oct(db_file.stat().st_mode & 0o777)
        assert mode == "0o600"
