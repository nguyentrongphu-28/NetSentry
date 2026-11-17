from __future__ import annotations

from app.domain.entities.finding import Finding, Severity
from app.domain.entities.parsed_config import ParsedConfig
from app.rules.base_rule import BaseRule

MAX_EXEC_TIMEOUT_SECONDS = 600


class VtyExecTimeoutRule(BaseRule):
    """Audit rule to enforce VTY executive session timeout (NET-005)."""

    rule_id = "NET-005"
    title = "Enforce VTY executive session timeout"
    severity = Severity.MEDIUM
    platforms = ("cisco_ios",)
    description = (
        "Idle VTY sessions without an exec-timeout or with excessively long "
        "timeouts leave management sessions vulnerable to unauthorized access."
    )
    remediation_text = (
        f'Configure "exec-timeout 10 0" or less (max {MAX_EXEC_TIMEOUT_SECONDS}s) '
        'under all "line vty" blocks.'
    )
    verification_text = (
        'Run "show running-config | section line vty" and verify exec-timeout is <= '
        f"{MAX_EXEC_TIMEOUT_SECONDS} seconds."
    )

    def check(self, config: ParsedConfig) -> list[Finding]:
        vty_blocks = config.blocks_starting_with("line vty")
        if not vty_blocks:
            return [
                self._unknown(
                    reason="No VTY lines found in configuration to evaluate exec-timeout."
                )
            ]

        fail_evidences: list[str] = []
        missing_vty_headers: list[str] = []
        pass_evidences: list[str] = []

        for block in vty_blocks:
            timeout_lines = block.child_starting_with("exec-timeout")
            if not timeout_lines:
                missing_vty_headers.append(block.header)
                continue

            for t_line in timeout_lines:
                parts = t_line.split()
                # Syntax: exec-timeout <minutes> [<seconds>]
                try:
                    minutes = int(parts[1]) if len(parts) > 1 else 0
                    seconds = int(parts[2]) if len(parts) > 2 else 0
                except (ValueError, IndexError):
                    fail_evidences.append(f"{block.header}: {t_line} (unparseable)")
                    continue

                total_seconds = minutes * 60 + seconds
                if total_seconds == 0:
                    fail_evidences.append(
                        f"{block.header}: {t_line} (timeout disabled)"
                    )
                elif total_seconds > MAX_EXEC_TIMEOUT_SECONDS:
                    fail_evidences.append(
                        f"{block.header}: {t_line} ({total_seconds}s > {MAX_EXEC_TIMEOUT_SECONDS}s)"
                    )
                else:
                    pass_evidences.append(f"{block.header}: {t_line}")

        # Priority: FAIL > UNKNOWN > PASS
        if fail_evidences:
            return [
                self._fail(
                    evidence=fail_evidences,
                    rationale=(
                        "One or more VTY blocks have disabled or excessive exec-timeout: "
                        f"{', '.join(fail_evidences)}."
                    ),
                )
            ]

        if missing_vty_headers:
            return [
                self._unknown(
                    reason=(
                        "One or more VTY blocks lack explicit 'exec-timeout' "
                        f"configuration: {', '.join(missing_vty_headers)}. "
                        "Cisco IOS default timeout is 10 minutes."
                    ),
                    evidence=tuple(missing_vty_headers),
                )
            ]

        return [
            self._pass(
                evidence=pass_evidences,
                note=f"All VTY blocks enforce an exec-timeout <= {MAX_EXEC_TIMEOUT_SECONDS}s.",
            )
        ]
