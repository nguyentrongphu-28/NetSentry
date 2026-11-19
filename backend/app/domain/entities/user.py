"""User and Role domain entities for NetSentry RBAC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")


class Role(str, Enum):
    """User roles for role-based access control."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


@dataclass(frozen=True)
class User:
    """Domain representation of a user (safe to expose, no password hash)."""

    id: int
    username: str
    role: Role
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None


@dataclass(frozen=True)
class UserWithHash:
    """Internal user representation holding password hash (used strictly by AuthService)."""

    id: int
    username: str
    password_hash: str
    role: Role
    is_active: bool
    must_change_password: bool
    failed_attempts: int
    locked_until: datetime | None
    created_at: datetime
    last_login_at: datetime | None

    def to_user(self) -> User:
        """Convert to safe User entity without password hash or internal counters."""
        return User(
            id=self.id,
            username=self.username,
            role=self.role,
            is_active=self.is_active,
            must_change_password=self.must_change_password,
            created_at=self.created_at,
            last_login_at=self.last_login_at,
        )
