"""Unit tests for AuthService, UserService, and SecurityEventService (Sections 9.3 & 9.4)."""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.domain.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    LastAdminError,
    RateLimitedError,
    WeakPasswordError,
)
from app.repositories.database import init_db
from app.repositories.sqlite_security_event_repository import SQLiteSecurityEventRepository
from app.repositories.sqlite_session_repository import SQLiteSessionRepository
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher
from app.security.rate_limiter import InMemorySlidingWindowLimiter
from app.security.tokens import hash_token
from app.services.auth_service import AuthService
from app.services.security_event_service import SecurityEventService
from app.services.user_service import UserService


class FakeClock:
    def __init__(self, start_time: datetime) -> None:
        self.current = start_time

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current = datetime.fromtimestamp(
            self.current.timestamp() + seconds,
            tz=timezone.utc,
        )


@pytest.fixture
def auth_stack(tmp_path: Path):
    db_file = tmp_path / "test_services.db"
    init_db(db_file)

    clock = FakeClock(datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc))
    hasher = Argon2PasswordHasher()
    limiter = InMemorySlidingWindowLimiter(max_requests=5, window_seconds=300)

    user_repo = SQLiteUserRepository(db_file)
    session_repo = SQLiteSessionRepository(db_file)
    event_repo = SQLiteSecurityEventRepository(db_file)

    auth_svc = AuthService(
        user_repo=user_repo,
        session_repo=session_repo,
        event_repo=event_repo,
        password_hasher=hasher,
        rate_limiter=limiter,
        max_failed_logins=3,
        lockout_minutes=15,
        session_ttl_minutes=480,
        clock=clock,
    )
    user_svc = UserService(
        user_repo=user_repo,
        session_repo=session_repo,
        event_repo=event_repo,
        password_hasher=hasher,
        clock=clock,
    )
    event_svc = SecurityEventService(
        event_repo=event_repo,
        clock=clock,
    )

    return {
        "auth_svc": auth_svc,
        "user_svc": user_svc,
        "event_svc": event_svc,
        "user_repo": user_repo,
        "session_repo": session_repo,
        "event_repo": event_repo,
        "clock": clock,
        "hasher": hasher,
        "limiter": limiter,
    }


class TestAuthService:
    def test_login_success(self, auth_stack) -> None:
        auth_svc = auth_stack["auth_svc"]
        user_svc = auth_stack["user_svc"]
        session_repo = auth_stack["session_repo"]

        user = user_svc.create_user("alice", "CorrectPassword123!", Role.ADMIN)
        logged_in_user, raw_token = auth_svc.login("alice", "CorrectPassword123!", client_ip="192.168.1.10")

        assert logged_in_user.username == "alice"
        assert len(raw_token) >= 32

        # Assert token is saved as SHA-256 hash in database, raw token is never stored
        token_digest = hash_token(raw_token)
        valid = session_repo.get_valid(token_digest, now=auth_stack["clock"](), idle_minutes=30)
        assert valid is not None
        assert valid[0].username == "alice"

        # Raw token query returns None
        assert session_repo.get_valid(raw_token, now=auth_stack["clock"](), idle_minutes=30) is None

    def test_uniform_error_for_nonexistent_user_and_wrong_password(self, auth_stack) -> None:
        auth_svc = auth_stack["auth_svc"]
        user_svc = auth_stack["user_svc"]
        user_svc.create_user("alice", "CorrectPassword123!", Role.OPERATOR)

        # 1. Nonexistent user
        with pytest.raises(InvalidCredentialsError) as exc_nonexistent:
            auth_svc.login("nonexistent", "SomePassword123!")
        assert exc_nonexistent.value.message == "Invalid username or password"

        # 2. Wrong password for existing user
        with pytest.raises(InvalidCredentialsError) as exc_wrong_pwd:
            auth_svc.login("alice", "WrongPassword123!")
        assert exc_wrong_pwd.value.message == "Invalid username or password"

    def test_account_lockout_after_max_failed_attempts(self, auth_stack) -> None:
        auth_svc = auth_stack["auth_svc"]
        user_svc = auth_stack["user_svc"]
        clock = auth_stack["clock"]

        user_svc.create_user("bob", "SecretPassword123!", Role.VIEWER)

        # 3 failed attempts (max=3)
        for _ in range(3):
            with pytest.raises(InvalidCredentialsError):
                auth_svc.login("bob", "WrongPassword123!")

        # 4th attempt raises AccountLockedError
        with pytest.raises(AccountLockedError, match="Account is temporarily locked"):
            auth_svc.login("bob", "SecretPassword123!")

        # Advance clock by 15.1 minutes -> lockout expires
        clock.advance(15.1 * 60)
        logged_in, _ = auth_svc.login("bob", "SecretPassword123!")
        assert logged_in.username == "bob"

    def test_inactive_user_cannot_login(self, auth_stack) -> None:
        auth_svc = auth_stack["auth_svc"]
        user_svc = auth_stack["user_svc"]

        user = user_svc.create_user("inactive_user", "ValidPassword123!", Role.VIEWER)
        user_svc.update_role_active(user.id, is_active=False)

        with pytest.raises(InvalidCredentialsError, match="Invalid username or password"):
            auth_svc.login("inactive_user", "ValidPassword123!")

    def test_change_password_revokes_other_sessions(self, auth_stack) -> None:
        auth_svc = auth_stack["auth_svc"]
        user_svc = auth_stack["user_svc"]
        session_repo = auth_stack["session_repo"]
        clock = auth_stack["clock"]

        user = user_svc.create_user("charlie", "OldPassword12345!", Role.OPERATOR)
        _, token1 = auth_svc.login("charlie", "OldPassword12345!")
        _, token2 = auth_svc.login("charlie", "OldPassword12345!")

        # Change password using token2 as current session
        auth_svc.change_password(
            user_id=user.id,
            current_password="OldPassword12345!",
            new_password="NewSecurePassword2026!",
            current_raw_token=token2,
        )

        now = clock()
        # token1 must be revoked, token2 must remain valid
        assert session_repo.get_valid(hash_token(token1), now=now, idle_minutes=30) is None
        assert session_repo.get_valid(hash_token(token2), now=now, idle_minutes=30) is not None

        # must_change_password must be False
        fresh_user = user_svc.get_user(user.id)
        assert fresh_user is not None
        assert fresh_user.must_change_password is False


class TestUserService:
    def test_last_admin_protection_on_demote_and_deactivate(self, auth_stack) -> None:
        user_svc = auth_stack["user_svc"]

        admin1 = user_svc.create_user("admin1", "AdminPassword123!", Role.ADMIN)
        admin2 = user_svc.create_user("admin2", "AdminPassword456!", Role.ADMIN)

        # Demote admin2 -> 1 admin remains
        user_svc.update_role_active(admin2.id, role=Role.OPERATOR)

        # Attempt to demote or deactivate the last remaining admin (admin1) -> LastAdminError
        with pytest.raises(LastAdminError, match="Cannot deactivate or demote"):
            user_svc.update_role_active(admin1.id, role=Role.VIEWER)

        with pytest.raises(LastAdminError, match="Cannot deactivate or demote"):
            user_svc.update_role_active(admin1.id, is_active=False)

    def test_reset_password_forces_must_change_and_revokes_sessions(self, auth_stack) -> None:
        auth_svc = auth_stack["auth_svc"]
        user_svc = auth_stack["user_svc"]
        session_repo = auth_stack["session_repo"]

        user = user_svc.create_user("operator_x", "InitPassword123!", Role.OPERATOR)
        _, token = auth_svc.login("operator_x", "InitPassword123!")

        # Admin resets password
        user_svc.reset_password(user.id, "AdminGivenTempPassword123!")

        # Session revoked
        assert session_repo.get_valid(hash_token(token), now=auth_stack["clock"](), idle_minutes=30) is None

        # must_change_password is True
        fresh = user_svc.get_user(user.id)
        assert fresh is not None
        assert fresh.must_change_password is True

        # Can login with new password
        logged_in, _ = auth_svc.login("operator_x", "AdminGivenTempPassword123!")
        assert logged_in.username == "operator_x"


class TestSecurityEventService:
    def test_record_and_list_events(self, auth_stack) -> None:
        event_svc = auth_stack["event_svc"]

        event_svc.record(
            event_type=SecurityEventType.USER_CREATED,
            actor_username="admin1",
            client_ip="127.0.0.1",
            target="user2",
            detail="Created user",
        )

        events = event_svc.list_events()
        assert len(events) >= 1
        assert events[0].event_type == SecurityEventType.USER_CREATED
        assert events[0].actor_username == "admin1"
