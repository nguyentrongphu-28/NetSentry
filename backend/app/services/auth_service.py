"""Authentication service managing login, session tokens, and password changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import User
from app.domain.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    RateLimitedError,
    ReauthFailedError,
    WeakPasswordError,
)
from app.domain.interfaces.security_event_repository import SecurityEventRepository
from app.domain.interfaces.session_repository import SessionRepository
from app.domain.interfaces.user_repository import UserRepository
from app.security.password_hasher import PasswordHasher
from app.security.password_policy import validate_password_strength
from app.security.rate_limiter import InMemorySlidingWindowLimiter
from app.security.tokens import TokenGenerator, hash_token



class AuthService:
    """Core domain service for user authentication and session management."""

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        event_repo: SecurityEventRepository,
        password_hasher: PasswordHasher,
        rate_limiter: InMemorySlidingWindowLimiter,
        max_failed_logins: int = 5,
        lockout_minutes: int = 15,
        session_ttl_minutes: int = 480,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._session_repo = session_repo
        self._event_repo = event_repo
        self._hasher = password_hasher
        self._dummy_hash = password_hasher.hash("dummy_password")  # generated at init for constant‑time verification

        self._limiter = rate_limiter
        self._max_failed_logins = max_failed_logins
        self._lockout_minutes = lockout_minutes
        self._session_ttl_minutes = session_ttl_minutes
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        dt = self._clock()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def login(
        self,
        username: str,
        password: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str]:
        """Authenticate user and return (User, raw_session_token).

        Flow:
        1. Rate limit by client_ip -> RateLimitedError
        2. Lookup user (dummy verify if not found -> uniform response time)
        3. Check account lockout -> AccountLockedError
        4. Check is_active -> InvalidCredentialsError
        5. Verify password:
           - On failure: increment attempts, lock if >= max, record LOGIN_LOCKED, raise InvalidCredentialsError
           - On success: reset attempts, update last_login, check rehash, create session, record LOGIN_SUCCESS
        """
        ip_key = client_ip or "unknown"
        allowed, retry_after = self._limiter.is_allowed(ip_key)
        if not allowed:
            raise RateLimitedError(
                "Too many login attempts. Please try again later.",
                retry_after=retry_after,
            )

        now = self._now()
        norm_username = username.strip().lower()
        user_record = self._user_repo.get_by_username(norm_username)

        # 1. Nonexistent user -> execute dummy verify and raise generic invalid credentials
        if not user_record:
            self._hasher.verify(self._dummy_hash, password)
            self._event_repo.add(
                occurred_at=now,
                event_type=SecurityEventType.LOGIN_FAILED,
                actor_username=None,
                client_ip=client_ip,
                target="auth",
                 detail="Unknown username",  
            )
            raise InvalidCredentialsError("Invalid username or password")

        # 2. Check if account is locked
        if user_record.locked_until and user_record.locked_until > now:
            self._event_repo.add(
                occurred_at=now,
                event_type=SecurityEventType.LOGIN_LOCKED,
                actor_username=norm_username,
                client_ip=client_ip,
                target=norm_username,
                detail="Login attempted on locked account",
            )
            raise AccountLockedError("Account is temporarily locked. Please try again later.")

        # 3. Check if user is active
        if not user_record.is_active:
            self._hasher.verify(self._dummy_hash, password)
            self._event_repo.add(
                occurred_at=now,
                event_type=SecurityEventType.LOGIN_FAILED,
                actor_username=norm_username,
                client_ip=client_ip,
                target=norm_username,
                detail="Login attempted on inactive account",
            )
            raise InvalidCredentialsError("Invalid username or password")

        # 4. Verify password
        is_valid = self._hasher.verify(user_record.password_hash, password)
        if not is_valid:
            attempts, locked_until = self._user_repo.register_failed_attempt(
                user_record.id,
                at=now,
                max_attempts=self._max_failed_logins,
                lock_minutes=self._lockout_minutes,
            )
            if locked_until is not None:
                self._event_repo.add(
                    occurred_at=now,
                    event_type=SecurityEventType.LOGIN_LOCKED,
                    actor_username=norm_username,
                    client_ip=client_ip,
                    target=norm_username,
                    detail=f"Account locked after {attempts} failed attempts",
                )
            else:
                self._event_repo.add(
                    occurred_at=now,
                    event_type=SecurityEventType.LOGIN_FAILED,
                    actor_username=norm_username,
                    client_ip=client_ip,
                    target=norm_username,
                    detail="Invalid username or password",
                )
            raise InvalidCredentialsError("Invalid username or password")

        # 5. Success: reset failed attempts
        self._user_repo.record_login_success(user_record.id, at=now)

        # Optional rehash check
        if self._hasher.needs_rehash(user_record.password_hash):
            new_hash = self._hasher.hash(password)
            self._user_repo.update_password(
                user_record.id,
                new_hash,
                must_change_password=user_record.must_change_password,
            )

        # Anti-session fixation: generate new random token
        raw_token = TokenGenerator.generate_token(32)
        token_digest = hash_token(raw_token)
        expires_at = datetime.fromtimestamp(
            now.timestamp() + (self._session_ttl_minutes * 60),
            tz=timezone.utc,
        )

        self._session_repo.create(
            token_hash=token_digest,
            user_id=user_record.id,
            created_at=now,
            expires_at=expires_at,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        self._event_repo.add(
            occurred_at=now,
            event_type=SecurityEventType.LOGIN_SUCCESS,
            actor_username=norm_username,
            client_ip=client_ip,
            target=norm_username,
            detail="User logged in successfully",
        )

        return user_record.to_user(), raw_token

    def logout(self, raw_token: str, actor_username: str | None = None, client_ip: str | None = None) -> None:
        """Revoke the current session token."""
        token_digest = hash_token(raw_token)
        self._session_repo.delete(token_digest)
        self._event_repo.add(
            occurred_at=self._now(),
            event_type=SecurityEventType.LOGOUT,
            actor_username=actor_username,
            client_ip=client_ip,
            target=actor_username,
            detail="User logged out",
        )
    def _verify_and_handle_password_attempt(
        self,
        user_id: int,
        password: str,
        client_ip: str | None = None,
        context: str = "reauth",
    ) -> None:
        now = self._now()
        user = self._user_repo.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError("User not found.")
        full_record = self._user_repo.get_by_username(user.username)
        if full_record is None:
            raise InvalidCredentialsError("User not found.")

        if full_record.locked_until and full_record.locked_until > now:
            self._event_repo.add(
                occurred_at=now,
                event_type=SecurityEventType.LOGIN_LOCKED,
                actor_username=user.username,
                client_ip=client_ip,
                target=user.username,
                detail=f"Attempt on locked account during {context}",
            )
            raise AccountLockedError("Account is temporarily locked. Please try again later.")

        if not self._hasher.verify(full_record.password_hash, password):
            _, locked_until = self._user_repo.register_failed_attempt(
                user_id,
                at=now,
                max_attempts=self._max_failed_logins,
                lock_minutes=self._lockout_minutes,
            )
            self._event_repo.add(
                occurred_at=now,
                event_type=(
                    SecurityEventType.LOGIN_LOCKED
                    if locked_until is not None
                    else SecurityEventType.LOGIN_FAILED
                ),
                actor_username=user.username,
                client_ip=client_ip,
                target=user.username,
                detail=f"Wrong password on {context}",
            )
            if locked_until is not None:
                self._session_repo.delete_all_for_user(user_id)
                raise AccountLockedError("Account is temporarily locked. Please try again later.")
            if context == "change-password":
                raise InvalidCurrentPasswordError("Current password is incorrect.")
            raise ReauthFailedError("Invalid password for re-authentication.")

    def verify_password_for_user(
        self,
        user_id: int,
        password: str,
        client_ip: str | None = None,
    ) -> None:
        """Verify user's password for step-up actions (e.g. remediation approval).

        On failure, increments failed attempts, records LOGIN_FAILED / LOGIN_LOCKED,
        revokes sessions if locked, and raises ReauthFailedError or AccountLockedError.
        """
        self._verify_and_handle_password_attempt(
            user_id=user_id,
            password=password,
            client_ip=client_ip,
            context="step-up-reauth",
        )

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        current_raw_token: str | None = None,
        client_ip: str | None = None,
    ) -> None:
        """Change password, revoke other sessions, clear must_change_password."""
        now = self._now()
        user = self._user_repo.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError("User not found.")

        self._verify_and_handle_password_attempt(
            user_id=user_id,
            password=current_password,
            client_ip=client_ip,
            context="change-password",
        )

        if current_password == new_password:
            raise WeakPasswordError("New password must be different from current password.")

        validate_password_strength(new_password, username=user.username)

        new_hash = self._hasher.hash(new_password)
        self._user_repo.update_password(user_id, new_hash, must_change_password=False)

        except_hash = hash_token(current_raw_token) if current_raw_token else None
        self._session_repo.delete_all_for_user(user_id, except_token_hash=except_hash)

        self._event_repo.add(
            occurred_at=now,
            event_type=SecurityEventType.PASSWORD_CHANGED,
            actor_username=user.username,
            client_ip=client_ip,
            target=user.username,
            detail="Password changed successfully",
        )
