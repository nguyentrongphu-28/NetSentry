"""Abstract interface for session repository."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.user import User


class SessionRepository(ABC):
    """Abstract contract for storing and validating user sessions."""

    @abstractmethod
    def create(
        self,
        token_hash: str,
        user_id: int,
        created_at: datetime,
        expires_at: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Create a new session record keyed by SHA-256 token hash."""
        raise NotImplementedError

    @abstractmethod
    def get_valid(
        self,
        token_hash: str,
        now: datetime,
        idle_minutes: int,
    ) -> tuple[User, datetime] | None:
        """Return (user, last_seen_at) if session is valid and user is active.

        Returns None if expired, idle timeout exceeded, or user inactive/not found.
        """
        raise NotImplementedError

    @abstractmethod
    def touch(self, token_hash: str, now: datetime) -> None:
        """Update last_seen_at for session."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, token_hash: str) -> None:
        """Delete session with the given token hash."""
        raise NotImplementedError

    @abstractmethod
    def delete_all_for_user(
        self,
        user_id: int,
        except_token_hash: str | None = None,
    ) -> int:
        """Revoke all sessions for user, optionally preserving one session."""
        raise NotImplementedError

    @abstractmethod
    def purge_expired(self, now: datetime) -> int:
        """Delete sessions where expires_at <= now. Returns number of purged sessions."""
        raise NotImplementedError
