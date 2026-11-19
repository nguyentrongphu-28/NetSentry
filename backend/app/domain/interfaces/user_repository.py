"""Abstract interface for user repository."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.user import Role, User, UserWithHash


class UserRepository(ABC):
    """Abstract contract for storing and managing users and credentials."""

    @abstractmethod
    def add(
        self,
        username: str,
        password_hash: str,
        role: Role,
        must_change_password: bool = True,
    ) -> User:
        """Add a new user with password hash.

        Raises UserExistsError if username already exists.
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None:
        """Return User by id or None if not found."""
        raise NotImplementedError

    @abstractmethod
    def get_by_username(self, username: str) -> UserWithHash | None:
        """Return UserWithHash by username (case-insensitive lookup, normalized)."""
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[User]:
        """Return all users ordered by id ascending."""
        raise NotImplementedError

    @abstractmethod
    def update_role_active(
        self,
        user_id: int,
        role: Role | None = None,
        is_active: bool | None = None,
    ) -> User:
        """Update role and/or is_active flag for a user.

        Raises UserNotFoundError if user does not exist.
        """
        raise NotImplementedError

    @abstractmethod
    def update_password(
        self,
        user_id: int,
        password_hash: str,
        must_change_password: bool = False,
    ) -> None:
        """Update user password hash and must_change_password flag.

        Raises UserNotFoundError if user does not exist.
        """
        raise NotImplementedError

    @abstractmethod
    def record_login_success(self, user_id: int, at: datetime) -> None:
        """Reset failed attempts, clear locked_until, and update last_login_at."""
        raise NotImplementedError

    @abstractmethod
    def register_failed_attempt(
        self,
        user_id: int,
        at: datetime,
        max_attempts: int,
        lock_minutes: int,
    ) -> tuple[int, datetime | None]:
        """Increment failed_attempts; if >= max_attempts set locked_until = at + lock_minutes.

        Returns (new_failed_attempts, locked_until).
        """
        raise NotImplementedError

    @abstractmethod
    def count_active_admins(self) -> int:
        """Count active users with role=admin."""
        raise NotImplementedError
