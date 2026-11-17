from __future__ import annotations

from app.domain.entities.finding import Finding, Severity
from app.domain.entities.parsed_config import ParsedConfig
from app.rules.base_rule import BaseRule


class SnmpCommunityRule(BaseRule):
    """Audit rule to disallow insecure SNMP community strings (NET-007)."""

    rule_id = "NET-007"
    title = "Disallow insecure SNMP community strings"
    severity = Severity.MEDIUM
    platforms = ("cisco_ios",)
    description = (
        "SNMPv1/v2c community strings transmit authentication credentials in cleartext. "
        "Read-write (RW) communities or default names ('public', 'private') allow "
        "unauthorized device reconfiguration or information leakage."
    )
    remediation_text = (
        "Remove community strings using 'no snmp-server community <string>' and migrate "
        "to SNMPv3 with SHA authentication and AES encryption."
    )
    verification_text = (
        'Run "show running-config | include snmp-server community" and verify no '
        "community strings are active."
    )

    def check(self, config: ParsedConfig) -> list[Finding]:
        comm_lines = config.global_starting_with("snmp-server community")
        if not comm_lines:
            return [
                self._pass(
                    note="No SNMP community strings configured (SNMPv3 configuration not evaluated).",
                )
            ]

        # Determine severity escalation:
        # HIGH if any community is RW or community name is 'public' or 'private'
        escalate_to_high = False
        for line in comm_lines:
            tokens = line.split()
            # Syntax: snmp-server community <name> [RO|RW] ...
            if len(tokens) >= 3:
                comm_name = tokens[2].lower()
                if comm_name in ("public", "private"):
                    escalate_to_high = True
                for opt in tokens[3:]:
                    if opt.upper() == "RW":
                        escalate_to_high = True

        effective_severity = Severity.HIGH if escalate_to_high else Severity.MEDIUM

        return [
            self._fail(
                evidence=comm_lines,
                rationale=(
                    "Insecure SNMP community strings found in configuration "
                    f"({'elevated to HIGH due to RW or default name' if escalate_to_high else 'MEDIUM'})."
                ),
                severity=effective_severity,
            )
        ]
