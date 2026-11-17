from __future__ import annotations

from app.domain.entities.finding import Finding, Severity
from app.domain.entities.parsed_config import ParsedConfig
from app.rules.base_rule import BaseRule


class HttpServerRule(BaseRule):
    """Audit rule to disable unencrypted HTTP server (NET-008)."""

    rule_id = "NET-008"
    title = "Disable unencrypted HTTP server"
    severity = Severity.MEDIUM
    platforms = ("cisco_ios",)
    description = (
        "The Cisco IOS unencrypted HTTP server transmits credentials and configuration "
        "data in plaintext over TCP port 80."
    )
    remediation_text = (
        "Disable unencrypted HTTP server using 'no ip http server'. "
        "Use 'ip http secure-server' (HTTPS) if web management is required."
    )
    verification_text = (
        'Run "show running-config | include ip http server" and verify unencrypted '
        "HTTP server is disabled or absent."
    )

    def check(self, config: ParsedConfig) -> list[Finding]:
        # If explicitly disabled via 'no ip http server', it is PASS
        if config.has_global("no ip http server"):
            return [
                self._pass(
                    evidence=("no ip http server",),
                    note="Unencrypted HTTP server is explicitly disabled.",
                )
            ]

        # Check for unencrypted HTTP server command
        # Note: 'ip http secure-server' is HTTPS and is NOT a violation
        unencrypted_http_lines = [
            line
            for line in config.global_lines
            if line.strip().lower() == "ip http server"
            or line.strip().lower().startswith("ip http server ")
        ]

        if unencrypted_http_lines:
            return [
                self._fail(
                    evidence=unencrypted_http_lines,
                    rationale="Unencrypted HTTP server is enabled ('ip http server').",
                )
            ]

        return [
            self._pass(
                note="Unencrypted HTTP server is not enabled.",
            )
        ]
