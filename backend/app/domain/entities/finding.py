from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    title: str
    severity: Severity
    status: FindingStatus
    evidence: tuple[str, ...]
    rationale: str
    remediation: str
    verification: str
    device_id: str | None = None
    checked_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": str(self.severity),
            "status": str(self.status),
            "evidence": list(self.evidence),
            "rationale": self.rationale,
            "remediation": self.remediation,
            "verification": self.verification,
            "device_id": self.device_id,
            "checked_at": self.checked_at.isoformat() if self.checked_at is not None else None,
        }
