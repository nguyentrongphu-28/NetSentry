"""Common Pydantic schemas for NetSentry API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    field: str
    message: str
    model_config = ConfigDict(extra="forbid")


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(BaseModel):
    error: ErrorPayload
    model_config = ConfigDict(extra="forbid")
