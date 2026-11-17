from __future__ import annotations

from app.domain.entities.finding import Finding, Severity
from app.domain.entities.parsed_config import ParsedConfig
from app.rules.base_rule import BaseRule


class TelnetRule(BaseRule):
    """Audit rule to ensure Telnet is disallowed on VTY lines (NET-001)."""

    rule_id = "NET-001"
    title = "Disallow Telnet on VTY lines"
    severity = Severity.HIGH
    platforms = ("cisco_ios",)
    description = (
        "Telnet transmits credentials and traffic in plaintext, exposing "
        "the device to interception and eavesdropping."
    )
    remediation_text = (
        'Restrict VTY lines to SSH: under "line vty" blocks configure "transport input ssh".'
    )
    verification_text = (
        'Run "show running-config | section line vty" and confirm transport input '
        "contains only secure protocols (e.g., ssh)."
    )

    def check(self, config: ParsedConfig) -> list[Finding]:
        vty_blocks = config.blocks_starting_with("line vty")
        if not vty_blocks:
            return [
                self._unknown(
                    reason="No VTY lines found in configuration to evaluate Telnet restriction."
                )
            ]

        fail_evidences: list[str] = []
        missing_vty_headers: list[str] = []
        pass_evidences: list[str] = []

        for block in vty_blocks:
            transport_lines = block.child_starting_with("transport input")
            if not transport_lines:
                missing_vty_headers.append(block.header)
                continue

            for t_line in transport_lines:
                tokens = t_line.lower().split()[2:]  # tokens after 'transport input'
                if "telnet" in tokens or "all" in tokens:
                    fail_evidences.append(f"{block.header}: {t_line}")
                else:
                    pass_evidences.append(f"{block.header}: {t_line}")

        # Priority: FAIL > UNKNOWN > PASS
        if fail_evidences:
            return [
                self._fail(
                    evidence=fail_evidences,
                    rationale=(
                        "Telnet or unencrypted access ('all') is permitted on VTY lines: "
                        f"{', '.join(fail_evidences)}."
                    ),
                )
            ]

        if missing_vty_headers:
            return [
                self._unknown(
                    reason=(
                        "One or more VTY blocks lack explicit 'transport input' "
                        f"configuration: {', '.join(missing_vty_headers)}. "
                        "Default behavior varies by Cisco IOS release."
                    ),
                    evidence=tuple(missing_vty_headers),
                )
            ]

        return [
            self._pass(
                evidence=pass_evidences,
                note="All VTY lines explicitly restrict transport input to secure protocols.",
            )
        ]
