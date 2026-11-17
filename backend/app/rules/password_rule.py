from __future__ import annotations

import re

from app.domain.entities.finding import Finding, Severity
from app.domain.entities.parsed_config import ParsedConfig
from app.rules.base_rule import BaseRule

_USERNAME_PASSWORD_PATTERN = re.compile(
    r"^\s*username\s+\S+.*?\bpassword\b",
    re.IGNORECASE,
)
_ENABLE_PASSWORD_PATTERN = re.compile(
    r"^\s*enable\s+password\b",
    re.IGNORECASE,
)


class PlainTextCredentialRule(BaseRule):
    """Audit rule to disallow plaintext or weakly encrypted passwords (NET-003)."""

    rule_id = "NET-003"
    title = "Disallow plaintext or weakly encrypted passwords"
    severity = Severity.HIGH
    platforms = ("cisco_ios",)
    description = (
        "Plaintext or weakly encrypted passwords (type 0 or type 7) expose "
        "credentials to unauthorized disclosure."
    )
    remediation_text = (
        "Replace 'enable password' with 'enable secret', and use 'username ... secret' "
        "instead of 'password'. Remove plaintext line passwords."
    )
    verification_text = (
        'Run "show running-config | include (password|secret)" and confirm only '
        "secure hashes ('secret') are used."
    )

    def check(self, config: ParsedConfig) -> list[Finding]:
        fail_evidences: list[str] = []

        # Check global lines for enable password and username ... password
        for line in config.global_lines:
            if _ENABLE_PASSWORD_PATTERN.search(line):
                fail_evidences.append(line)
            elif _USERNAME_PASSWORD_PATTERN.search(line):
                fail_evidences.append(line)

        # Check line blocks (line con, line aux, line vty) for password statements
        for block in config.blocks:
            if block.header.lower().startswith("line "):
                pwd_lines = block.child_starting_with("password")
                for p_line in pwd_lines:
                    fail_evidences.append(f"{block.header}: {p_line}")

        if fail_evidences:
            return [
                self._fail(
                    evidence=fail_evidences,
                    rationale="Plaintext or weakly encrypted passwords found in configuration.",
                )
            ]

        return [
            self._pass(
                note="No plaintext or weakly encrypted passwords found; secure hashes are used.",
            )
        ]


class PasswordEncryptionServiceRule(BaseRule):
    """Audit rule to ensure Cisco password encryption service is active (NET-004)."""

    rule_id = "NET-004"
    title = "Enable Cisco password encryption service"
    severity = Severity.LOW
    platforms = ("cisco_ios",)
    description = (
        "The password encryption service obscures passwords in the running configuration, "
        "preventing casual over-the-shoulder observation."
    )
    remediation_text = "Configure 'service password-encryption' in global configuration mode."
    verification_text = (
        'Run "show running-config | include service password-encryption" and verify '
        "the service is active."
    )

    def check(self, config: ParsedConfig) -> list[Finding]:
        has_service = config.has_global("service password-encryption")
        has_no_service = config.has_global("no service password-encryption")

        if has_service and not has_no_service:
            return [
                self._pass(
                    evidence=("service password-encryption",),
                    note="Service password-encryption is enabled.",
                )
            ]

        evidence: list[str] = []
        if has_no_service:
            evidence.append("no service password-encryption")

        return [
            self._fail(
                evidence=evidence,
                rationale="Service password-encryption is not enabled on the device.",
            )
        ]
