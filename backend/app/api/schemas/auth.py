"""Authentication schemas for request and response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Payload for POST /api/v1/auth/login."""

    username: str = Field(..., min_length=1, max_length=64, description="User username")
    password: str = Field(..., min_length=1, max_length=128, description="User password")


class ChangePasswordRequest(BaseModel):
    """Payload for POST /api/v1/auth/change-password."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=12, max_length=128)


class UserSummaryOut(BaseModel):
    """Public user summary."""

    id: int
    username: str
    role: str
    must_change_password: bool


class CapabilitiesOut(BaseModel):
    """Server security capabilities reported to frontend."""

    body_credentials: bool


class AuthMeResponse(BaseModel):
    """Response payload for GET /api/v1/auth/me."""

    user: UserSummaryOut
    capabilities: CapabilitiesOut


class LoginResponse(BaseModel):
    """Response payload for POST /api/v1/auth/login."""

    user: UserSummaryOut
