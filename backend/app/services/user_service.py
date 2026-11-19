"""User management service (admin operations, role updates, password reset)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role, User
from app.domain.errors import (
    LastAdminError,
    UserNotFoundError,
    WeakPasswordError,
)
from app.domain.interfaces.security_event_repository import SecurityEventRepository
from app.domain.interfaces.session_repository import SessionRepository
from app.domain.interfaces.user_repository import UserRepository
from app.security.password_hasher import PasswordHasher
from app.security.password_policy import validate_password_strength


class UserService:
    """Domain service for administrative user management."""

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        event_repo: SecurityEventRepository,
        password_hasher: PasswordHasher,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._session_repo = session_repo
        self._event_repo = event_repo
        self._hasher = password_hasher
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        dt = self._clock()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def create_user(
        self,
        username: str,
        password: str,
        role: Role,
        actor_username: str | None = None,
        client_ip: str | None = None,
    ) -> User:
        """Create new user with must_change_password=True."""
        validate_password_strength(password, username=username)

        password_hash = self._hasher.hash(password)
        user = self._user_repo.add(
            username=username,
            password_hash=password_hash,
            role=role,
            must_change_password=True,
        )

        self._event_repo.add(
            occurred_at=self._now(),
            event_type=SecurityEventType.USER_CREATED,
            actor_username=actor_username,
            client_ip=client_ip,
            target=user.username,
            detail=f"Created user with role {role.value}",
        )
        return user

    def list_users(self) -> list[User]:
        """List all users."""
        return self._user_repo.list()

    def get_user(self, user_id: int) -> User | None:
        """Get user by ID."""
        return self._user_repo.get_by_id(user_id)

    def update_role_active(
        self,
        user_id: int,
        role: Role | None = None,
        is_active: bool | None = None,
        actor_username: str | None = None,
        client_ip: str | None = None,
    ) -> User:
        """Update user role and/or active status.

        Last Admin Protection:
        Cannot deactivate or demote an active admin if no other active admin exists,
        even if the actor is operating on themselves.
        """
        existing = self._user_repo.get_by_id(user_id)
        if not existing:
            raise UserNotFoundError(f"User with ID {user_id} not found.")

        # Check Last Admin invariant if modifying an active admin
        if existing.role == Role.ADMIN and existing.is_active:
            will_demote = role is not None and role != Role.ADMIN
            will_deactivate = is_active is not None and is_active is False

            if will_demote or will_deactivate:
                active_admins = self._user_repo.count_active_admins()
                if active_admins <= 1:
                    raise LastAdminError(
                        "Cannot deactivate or demote the last remaining active administrator."
                    )

        updated = self._user_repo.update_role_active(
            user_id=user_id,
            role=role,
            is_active=is_active,
        )

        # Invalidate all existing sessions for this user on security change
        self._session_repo.delete_all_for_user(user_id)

        changes = []
        if role is not None:
            changes.append(f"role={role.value}")
        if is_active is not None:
            changes.append(f"active={is_active}")

        self._event_repo.add(
            occurred_at=self._now(),
            event_type=SecurityEventType.USER_UPDATED,
            actor_username=actor_username,
            client_ip=client_ip,
            target=updated.username,
            detail=f"Updated user: {', '.join(changes)}",
        )
        return updated

    def reset_password(
        self,
        user_id: int,
        new_password: str,
        actor_username: str | None = None,
        client_ip: str | None = None,
    ) -> None:
        """Reset user password (sets must_change_password=True and revokes all sessions)."""
        existing = self._user_repo.get_by_id(user_id)
        if not existing:
            raise UserNotFoundError(f"User with ID {user_id} not found.")

        validate_password_strength(new_password, username=existing.username)

        new_hash = self._hasher.hash(new_password)
        self._user_repo.update_password(user_id, new_hash, must_change_password=True)
        self._session_repo.delete_all_for_user(user_id)

        self._event_repo.add(
            occurred_at=self._now(),
            event_type=SecurityEventType.PASSWORD_RESET,
            actor_username=actor_username,
            client_ip=client_ip,
            target=existing.username,
            detail="Password reset by administrator",
        )
