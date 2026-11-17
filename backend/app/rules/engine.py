from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import replace
from datetime import datetime, timezone
import logging

from app.domain.entities.finding import Finding, FindingStatus
from app.domain.interfaces.audit_rule import AuditRule
from app.domain.interfaces.config_parser import ConfigParser

logger = logging.getLogger(__name__)


class RuleEngine:
    """Orchestrator for configuration audit rules execution."""

    def __init__(
        self,
        rules: Sequence[AuditRule],
        parser: ConfigParser,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        # Validate uniqueness of rule IDs
        seen_ids: set[str] = set()
        for r in rules:
            if r.rule_id in seen_ids:
                raise ValueError(f"Duplicate rule_id detected in RuleEngine: '{r.rule_id}'")
            seen_ids.add(r.rule_id)

        self._rules: tuple[AuditRule, ...] = tuple(rules)
        self._parser = parser
        self._clock: Callable[[], datetime] = (
            clock if clock is not None else (lambda: datetime.now(timezone.utc))
        )

    def run(
        self,
        config_text: str,
        platform: str = "cisco_ios",
        device_id: str | None = None,
        only_rule_ids: Collection[str] | None = None,
        skip_rule_ids: Collection[str] | None = None,
    ) -> list[Finding]:
        checked_at = self._clock()
        parsed_config = self._parser.parse(config_text)

        only_set = set(only_rule_ids) if only_rule_ids is not None else None
        skip_set = set(skip_rule_ids) if skip_rule_ids is not None else set()

        findings: list[Finding] = []

        for rule in self._rules:
            # Platform compatibility check
            if not rule.applies_to(platform):
                continue

            # Filtering rules
            if only_set is not None and rule.rule_id not in only_set:
                continue
            if rule.rule_id in skip_set:
                continue

            # Error isolation: rule failures do not interrupt engine run
            try:
                rule_findings = rule.check(parsed_config)
            except Exception as exc:
                # Log error without exposing configuration text
                logger.exception("Rule execution failure in %s", rule.rule_id)
                rule_findings = [
                    Finding(
                        rule_id=rule.rule_id,
                        title=rule.title,
                        severity=rule.severity,
                        status=FindingStatus.UNKNOWN,
                        evidence=(f"rule execution error: {type(exc).__name__}",),
                        rationale=f"Rule execution failed with exception: {type(exc).__name__}",
                        remediation=getattr(rule, "remediation_text", ""),
                        verification=getattr(rule, "verification_text", ""),
                    )
                ]

            for finding in rule_findings:
                # Stamp with device_id and checked_at
                stamped = replace(finding, device_id=device_id, checked_at=checked_at)
                findings.append(stamped)

        # Stable sort by rule_id ascending
        findings.sort(key=lambda f: f.rule_id)
        return findings
