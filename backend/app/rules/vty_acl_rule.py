from __future__ import annotations

from app.domain.entities.finding import Finding, Severity
from app.domain.entities.parsed_config import ParsedConfig
from app.rules.base_rule import BaseRule


class VtyAccessClassRule(BaseRule):
    """Audit rule to ensure VTY lines restrict access via ACL (NET-006)."""

    rule_id = "NET-006"
    title = "Restrict VTY access using Access Control List"
    severity = Severity.MEDIUM
    platforms = ("cisco_ios",)
    description = (
        "VTY lines without access-class restrictions permit inbound administrative "
        "connections from any IP address."
    )
    remediation_text = (
        'Configure "access-class <ACL_NAME_OR_NUMBER> in" under all "line vty" blocks.'
    )
    verification_text = (
        'Run "show running-config | section line vty" and verify access-class is applied '
        "in the inbound direction."
    )

    def check(self, config: ParsedConfig) -> list[Finding]:
        vty_blocks = config.blocks_starting_with("line vty")
        if not vty_blocks:
            return [
                self._unknown(
                    reason="No VTY lines found in configuration to evaluate access-class restrictions."
                )
            ]

        missing_acl_blocks: list[str] = []
        pass_evidences: list[str] = []

        for block in vty_blocks:
            acl_lines = block.child_starting_with("access-class")
            inbound_acl_found = False

            for a_line in acl_lines:
                tokens = a_line.lower().split()
                # Syntax: access-class <acl> in [vrf-also]
                if len(tokens) >= 3 and "in" in tokens[2:]:
                    inbound_acl_found = True
                    pass_evidences.append(f"{block.header}: {a_line}")

            if not inbound_acl_found:
                missing_acl_blocks.append(f"{block.header}: missing 'access-class ... in'")

        # Priority: FAIL > UNKNOWN > PASS
        if missing_acl_blocks:
            return [
                self._fail(
                    evidence=missing_acl_blocks,
                    rationale=(
                        "One or more VTY blocks lack inbound access-class restriction: "
                        f"{', '.join(missing_acl_blocks)}."
                    ),
                )
            ]

        return [
            self._pass(
                evidence=pass_evidences,
                note="All VTY lines enforce inbound access-class restriction (ACL contents not evaluated).",
            )
        ]
