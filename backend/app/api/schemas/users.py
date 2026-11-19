"""Schemas for administrative user management."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    """Payload for POST /api/v1/users."""

    username: str = Field(..., pattern=r"^[a-z0-9][a-z0-9._-]{2,31}$", description="Username (lowercase)")
    password: str = Field(..., min_length=12, max_length=128, description="Initial password")
    role: str = Field(..., pattern=r"^(admin|operator|viewer)$")


class UpdateUserRequest(BaseModel):
    """Payload for PATCH /api/v1/users/{id}."""

    role: str | None = Field(default=None, pattern=r"^(admin|operator|viewer)$")
    is_active: bool | None = Field(default=None)


class ResetPasswordRequest(BaseModel):
    """Payload for POST /api/v1/users/{id}/reset-password."""

    new_password: str = Field(..., min_length=12, max_length=128)


class UserOut(BaseModel):
    """User response object."""

    id: int
    username: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None
