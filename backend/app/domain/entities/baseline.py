"""Baseline entities and status enums."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class BaselineStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class Baseline:
    id: int
    device_id: str
    snapshot_id: int
    content_sha256: str
    status: BaselineStatus
    approved_by: str
    approved_at: datetime
    note: str | None
    fail_count_at_approval: int
    retired_at: datetime | None = None
    retired_by: str | None = None
