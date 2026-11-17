"""Domain entities representing audit run results stored in the repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.finding import Finding


@dataclass(frozen=True, slots=True)
class AuditRunSummary:
    """Summary of an audit run without individual findings."""

    id: int
    device_id: str
    platform: str
    status: AuditStatus
    started_at: datetime
    finished_at: datetime
    hostname: str | None
    error_code: str | None
    error_message: str | None
    pass_count: int
    fail_count: int
    unknown_count: int


@dataclass(frozen=True, slots=True)
class AuditRunDetail:
    """Full detail of an audit run including all findings."""

    summary: AuditRunSummary
    findings: tuple[Finding, ...]
