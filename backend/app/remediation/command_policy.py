"""Command allowlist and validation policy for remediation."""

from __future__ import annotations

from typing import Sequence

COMMAND_ALLOWLIST: frozenset[str] = frozenset({
    "no ip http server",
    "service password-encryption",
})

FORBIDDEN_TOKENS: tuple[str, ...] = (
    "reload",
    "erase",
    "delete",
    "format",
    "copy",
    "write",
    "configure",
    "conf t",
    "username",
    "enable",
    "crypto key",
    "tftp",
    "ftp",
    "scp",
    "boot",
    "shutdown",
    "transport",
    "access-class",
    "line ",
)


def validate_commands(commands: Sequence[str]) -> None:
    """Validate that commands conform strictly to human-verified fixed templates.

    Raises ValueError if commands list is empty, contains unauthorized commands,
    contains forbidden tokens, or has unexpected whitespace/formatting.
    """
    if not commands:
        raise ValueError("Remediation commands cannot be empty.")

    for cmd in commands:
        if not isinstance(cmd, str):
            raise ValueError(f"Command must be a string, got {type(cmd)}")

        if not cmd:
            raise ValueError("Command line cannot be empty.")

        if len(cmd) > 120:
            raise ValueError(f"Command exceeds maximum length of 120 chars: {cmd!r}")

        for forbidden in ("\n", "\r", ";", "|", "`"):
            if forbidden in cmd:
                raise ValueError(f"Command contains forbidden character {forbidden!r}: {cmd!r}")

        # Exact match check against allowlist (case-sensitive, strict string equality)
        if cmd not in COMMAND_ALLOWLIST:
            raise ValueError(f"Command is not in COMMAND_ALLOWLIST: {cmd!r}")

        # Check for forbidden tokens
        cmd_lower = cmd.lower()
        for token in FORBIDDEN_TOKENS:
            if token in cmd_lower:
                raise ValueError(f"Command contains forbidden token {token!r}: {cmd!r}")
