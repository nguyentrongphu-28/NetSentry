"""Pydantic schemas for device endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.audit import AuditRunSummaryOut
from app.domain.entities.audit_run import AuditRunSummary
from app.domain.entities.device import Device


class DeviceCreate(BaseModel):
    device_id: str = Field(..., pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    host: str = Field(..., min_length=1, max_length=253)
    name: str | None = Field(default=None, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    platform: Literal["cisco_ios"] = "cisco_ios"

    model_config = ConfigDict(extra="forbid")


class DeviceOut(BaseModel):
    device_id: str
    name: str
    host: str
    port: int
    platform: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_domain(cls, device: Device) -> DeviceOut:
        return cls(
            device_id=device.device_id,
            name=device.name,
            host=device.host,
            port=device.port,
            platform=device.platform,
            created_at=device.created_at,
            updated_at=device.updated_at,
        )


class DeviceWithLatestAuditOut(DeviceOut):
    latest_audit: AuditRunSummaryOut | None = None

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_domain_with_audit(
        cls, device: Device, latest_audit: AuditRunSummary | None = None
    ) -> DeviceWithLatestAuditOut:
        return cls(
            device_id=device.device_id,
            name=device.name,
            host=device.host,
            port=device.port,
            platform=device.platform,
            created_at=device.created_at,
            updated_at=device.updated_at,
            latest_audit=AuditRunSummaryOut.from_domain(latest_audit)
            if latest_audit is not None
            else None,
        )


class DeviceListOut(BaseModel):
    items: list[DeviceWithLatestAuditOut]

    model_config = ConfigDict(extra="forbid")
