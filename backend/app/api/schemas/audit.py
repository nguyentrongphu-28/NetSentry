"""Pydantic schemas for audits and findings."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.domain.entities.audit_run import AuditRunDetail, AuditRunSummary
from app.domain.entities.device import Credentials
from app.domain.entities.finding import Finding


class CredentialsIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: SecretStr
    enable_secret: SecretStr | None = None

    model_config = ConfigDict(extra="forbid")

    def to_domain(self) -> Credentials:
        return Credentials(
            username=self.username,
            password=self.password.get_secret_value(),
            enable_secret=self.enable_secret.get_secret_value() if self.enable_secret is not None else None,
        )


class AuditRequest(BaseModel):
    credentials: CredentialsIn | None = None

    model_config = ConfigDict(extra="forbid")


class AuditRunSummaryOut(BaseModel):
    id: int
    device_id: str
    platform: str
    status: Literal["COMPLETED", "FAILED"]
    started_at: datetime
    finished_at: datetime
    hostname: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    pass_count: int
    fail_count: int
    unknown_count: int

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_domain(cls, summary: AuditRunSummary) -> AuditRunSummaryOut:
        return cls(
            id=summary.id,
            device_id=summary.device_id,
            platform=summary.platform,
            status=summary.status.value if hasattr(summary.status, "value") else str(summary.status),  # type: ignore[arg-type]
            started_at=summary.started_at,
            finished_at=summary.finished_at,
            hostname=summary.hostname,
            error_code=summary.error_code,
            error_message=summary.error_message,
            pass_count=summary.pass_count,
            fail_count=summary.fail_count,
            unknown_count=summary.unknown_count,
        )


class FindingOut(BaseModel):
    rule_id: str
    title: str
    severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    evidence: list[str]
    rationale: str
    remediation: str
    verification: str
    checked_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_domain(cls, finding: Finding) -> FindingOut:
        return cls(
            rule_id=finding.rule_id,
            title=finding.title,
            severity=finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),  # type: ignore[arg-type]
            status=finding.status.value if hasattr(finding.status, "value") else str(finding.status),  # type: ignore[arg-type]
            evidence=list(finding.evidence),
            rationale=finding.rationale,
            remediation=finding.remediation,
            verification=finding.verification,
            checked_at=finding.checked_at,
        )


class AuditRunDetailOut(BaseModel):
    summary: AuditRunSummaryOut
    findings: list[FindingOut]

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_domain(cls, detail: AuditRunDetail) -> AuditRunDetailOut:
        return cls(
            summary=AuditRunSummaryOut.from_domain(detail.summary),
            findings=[FindingOut.from_domain(f) for f in detail.findings],
        )


class AuditRunListOut(BaseModel):
    items: list[AuditRunSummaryOut]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(extra="forbid")
