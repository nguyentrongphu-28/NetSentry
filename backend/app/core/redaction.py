from __future__ import annotations

import re

REDACTED = "<REDACTED>"

_REDACTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # enable password [0|7] <secret>
    re.compile(r"^(\s*enable\s+password(?:\s+\d+)?\s+)(\S+)(.*)$", re.IGNORECASE),
    # enable secret [type] <secret>
    re.compile(r"^(\s*enable\s+secret(?:\s+\d+)?\s+)(\S+)(.*)$", re.IGNORECASE),
    # username <user> ... password|secret [type] <secret>
    re.compile(r"^(\s*username\s+\S+.*?\s+(?:password|secret)(?:\s+\d+)?\s+)(\S+)(.*)$", re.IGNORECASE),
    # password [type] <secret> (standalone, in line block, or in evidence "<header>: password ...")
    re.compile(r"^(.*?\bpassword(?:\s+\d+)?\s+)(\S+)(.*)$", re.IGNORECASE),
    # snmp-server community <secret> ...
    re.compile(r"^(\s*snmp-server\s+community\s+)(\S+)(.*)$", re.IGNORECASE),
    # snmp-server host ... version 1|2c <secret> ...
    re.compile(r"^(\s*snmp-server\s+host\s+.*?\s+version\s+(?:1|2c)\s+)(\S+)(.*)$", re.IGNORECASE),
    # tacacs/radius/ntp/crypto ... key [type] <secret>
    re.compile(r"^(.*?\b(?:tacacs|radius|ntp|crypto\s+isakmp).*?\bkey(?:\s+\d+)?\s+)(\S+)(.*)$", re.IGNORECASE),
    re.compile(r"^(.*?\bkey\s+[07]\s+)(\S+)(.*)$", re.IGNORECASE),
)


def redact_line(line: str) -> str:
    """Redact sensitive credentials from a configuration or evidence line.

    Replaces passwords, secrets, SNMP communities, and pre-shared keys with
    ``<REDACTED>``. Preserves surrounding tokens, formatting, and indentation.
    Guaranteed to be idempotent and never raises an exception.
    """
    if not isinstance(line, str):
        return line

    try:
        result = line
        for pattern in _REDACTION_PATTERNS:
            match = pattern.match(result)
            if match:
                prefix = match.group(1)
                secret = match.group(2)
                suffix = match.group(3)
                if secret != REDACTED:
                    result = f"{prefix}{REDACTED}{suffix}"
        return result
    except Exception:
        return line
