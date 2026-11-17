from __future__ import annotations

from app.domain.entities.finding import Finding, Severity
from app.domain.entities.parsed_config import ParsedConfig
from app.rules.base_rule import BaseRule


class SshVersionRule(BaseRule):
    """Audit rule to enforce SSH version 2 (NET-002)."""

    rule_id = "NET-002"
    title = "Enforce SSH version 2"
    severity = Severity.MEDIUM
    platforms = ("cisco_ios",)
    description = (
        "SSH version 1 has cryptographic vulnerabilities and should not be used. "
        "SSH version 2 must be explicitly enforced."
    )
    remediation_text = "Configure 'ip ssh version 2' in global configuration mode."
    verification_text = 'Run "show ip ssh" and verify SSH version 2 is enabled.'

    def check(self, config: ParsedConfig) -> list[Finding]:
        # NET-002 only has PASS or FAIL, never UNKNOWN
        ssh_lines = config.global_starting_with("ip ssh version")

        # Check for explicit version 1
        v1_lines = [line for line in ssh_lines if line.lower().startswith("ip ssh version 1")]
        if v1_lines:
            return [
                self._fail(
                    evidence=v1_lines,
                    rationale="Insecure SSH version 1 is configured on the device.",
                )
            ]

        # Check for explicit version 2
        v2_lines = [line for line in ssh_lines if line.lower().startswith("ip ssh version 2")]
        if v2_lines:
            return [
                self._pass(
                    evidence=v2_lines,
                    note="SSH version 2 is explicitly enforced.",
                )
            ]

        # Missing explicit SSH version 2 configuration
        return [
            self._fail(
                evidence=(),
                rationale="SSH version 2 is not explicitly configured on the device.",
            )
        ]
