"""Schemas for security event queries."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class SecurityEventOut(BaseModel):
    """Security audit event record."""

    id: int
    occurred_at: datetime
    event_type: str
    actor_username: str | None
    client_ip: str | None
    target: str | None
    detail: str | None
