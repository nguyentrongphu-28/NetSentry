from __future__ import annotations

from collections.abc import Iterable

from app.core.redaction import redact_line
from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.interfaces.audit_rule import AuditRule


class BaseRule(AuditRule):
    """Base class for Cisco IOS audit rules providing consistent Finding generation.

    Ensures all evidence is redacted and findings follow standard formats.
    """

    description: str
    remediation_text: str
    verification_text: str

    def _pass(
        self,
        evidence: Iterable[str] = (),
        note: str | None = None,
    ) -> Finding:
        redacted_evidence = tuple(redact_line(e) for e in evidence)
        return Finding(
            rule_id=self.rule_id,
            title=self.title,
            severity=self.severity,
            status=FindingStatus.PASS,
            evidence=redacted_evidence,
            rationale=note or self.description,
            remediation=self.remediation_text,
            verification=self.verification_text,
        )

    def _fail(
        self,
        evidence: Iterable[str],
        rationale: str | None = None,
        severity: Severity | None = None,
    ) -> Finding:
        redacted_evidence = tuple(redact_line(e) for e in evidence)
        return Finding(
            rule_id=self.rule_id,
            title=self.title,
            severity=severity or self.severity,
            status=FindingStatus.FAIL,
            evidence=redacted_evidence,
            rationale=rationale or self.description,
            remediation=self.remediation_text,
            verification=self.verification_text,
        )

    def _unknown(
        self,
        reason: str,
        evidence: Iterable[str] = (),
    ) -> Finding:
        redacted_evidence = tuple(redact_line(e) for e in evidence)
        return Finding(
            rule_id=self.rule_id,
            title=self.title,
            severity=self.severity,
            status=FindingStatus.UNKNOWN,
            evidence=redacted_evidence,
            rationale=reason,
            remediation=self.remediation_text,
            verification=self.verification_text,
        )
