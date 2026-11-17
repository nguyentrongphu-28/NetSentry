"""Domain entity representing the result of a device audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.domain.entities.finding import Finding, FindingStatus


class AuditStatus(StrEnum):
    """Status of an audit run."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class AuditResult:
    """Outcome of auditing a target device."""

    device_id: str
    platform: str
    status: AuditStatus
    started_at: datetime
    finished_at: datetime
    findings: tuple[Finding, ...] = ()
    hostname: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def pass_count(self) -> int:
        return sum(1 for f in self.findings if f.status == FindingStatus.PASS or f.status == "PASS")

    @property
    def fail_count(self) -> int:
        return sum(1 for f in self.findings if f.status == FindingStatus.FAIL or f.status == "FAIL")

    @property
    def unknown_count(self) -> int:
        return sum(1 for f in self.findings if f.status == FindingStatus.UNKNOWN or f.status == "UNKNOWN")

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "platform": self.platform,
            "status": str(self.status),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "hostname": self.hostname,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "unknown_count": self.unknown_count,
            "findings": [f.to_dict() for f in self.findings],
        }
