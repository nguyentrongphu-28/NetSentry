"""Validator and sanitizer for LLM output (Spec 8.7)."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Sequence

from app.domain.entities.ai_explanation import AiExplanation, PriorityItem, RiskNote
from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.errors import AiOutputInvalidError

_COMMAND_LINE_PATTERNS = re.compile(
    r"^\s*(?:configure\b|conf\s+t\b|no\s+|ip\s+|line\s+|enable\s+|username\s+|"
    r"snmp-server\s+|service\s+|crypto\s+|reload\b|write\b|copy\b|erase\b)",
    re.IGNORECASE,
)
_HTML_MARKDOWN_LINK_PATTERN = re.compile(r"<[^>]+>|\[([^\]]+)\]\([^\)]+\)")
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ExplanationValidator:
    """Validates, strips dangerous command lines, and sanitizes untrusted LLM outputs."""

    @classmethod
    def sanitize_text(cls, text: str, max_len: int) -> str:
        if not text:
            return ""
        # Remove HTML and markdown links, keeping link text
        cleaned = _HTML_MARKDOWN_LINK_PATTERN.sub(r"\1", text)
        # Strip control characters
        cleaned = _CONTROL_CHAR_PATTERN.sub(" ", cleaned)

        # Remove lines that resemble Cisco IOS executable commands
        kept_lines = []
        for line in cleaned.splitlines():
            if _COMMAND_LINE_PATTERNS.match(line):
                continue
            kept_lines.append(line)

        result = "\n".join(kept_lines).strip()
        if len(result) > max_len:
            result = result[:max_len]
        return result

    @classmethod
    def validate(
        cls,
        raw_output: dict[str, Any],
        findings: Sequence[Finding],
        *,
        run_id: int = 0,
        created_at: datetime | None = None,
        model: str = "mock-model",
        prompt_version: int = 1,
        input_sha256: str = "mock-sha",
    ) -> AiExplanation:
        if not isinstance(raw_output, dict):
            raise AiOutputInvalidError("Output is not a dictionary")

        summary_raw = str(raw_output.get("summary") or "")
        summary = cls.sanitize_text(summary_raw, max_len=1200)
        if not summary:
            raise AiOutputInvalidError("Summary is empty after sanitization")

        valid_rule_ids = {f.rule_id for f in findings}
        fail_findings = [f for f in findings if f.status == FindingStatus.FAIL]

        # Process priorities
        raw_priorities = raw_output.get("priorities")
        if not isinstance(raw_priorities, list):
            raw_priorities = []

        priorities_list: list[PriorityItem] = []
        seen_priority_rules: set[str] = set()

        for item in raw_priorities:
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("rule_id") or "").strip()
            # Drop hallunicated rule IDs
            if rule_id not in valid_rule_ids or rule_id in seen_priority_rules:
                continue
            reason = cls.sanitize_text(str(item.get("reason") or ""), max_len=200)
            seen_priority_rules.add(rule_id)
            priorities_list.append(PriorityItem(rule_id=rule_id, reason=reason))

        # Ensure all FAIL findings are included in priorities in deterministic order
        # Sort fail findings: severity (CRITICAL > HIGH > MEDIUM > LOW > INFO), then rule_id
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }
        sorted_fail = sorted(
            fail_findings,
            key=lambda f: (severity_order.get(f.severity, 99), f.rule_id),
        )

        for f in sorted_fail:
            if f.rule_id not in seen_priority_rules:
                seen_priority_rules.add(f.rule_id)
                priorities_list.append(PriorityItem(rule_id=f.rule_id, reason=""))

        # Process risks
        raw_risks = raw_output.get("risks")
        if not isinstance(raw_risks, list):
            raw_risks = []

        risks_list: list[RiskNote] = []
        seen_risk_rules: set[str] = set()

        for item in raw_risks:
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("rule_id") or "").strip()
            if rule_id not in valid_rule_ids or rule_id in seen_risk_rules:
                continue
            warning = cls.sanitize_text(str(item.get("warning") or ""), max_len=200)
            seen_risk_rules.add(rule_id)
            risks_list.append(RiskNote(rule_id=rule_id, warning=warning))

        return AiExplanation(
            run_id=run_id,
            created_at=created_at or datetime.now(timezone.utc),
            model=model,
            prompt_version=prompt_version,
            input_sha256=input_sha256,
            summary=summary,
            priorities=tuple(priorities_list),
            risks=tuple(risks_list),
        )
