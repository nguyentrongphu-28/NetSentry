from __future__ import annotations

import re


class ConfigNormalizer:
    """Normalizes configuration text to remove non-deterministic and time-varying lines."""

    # Patterns for lines that vary between configurations without representing real intent changes
    _TIME_VARYING_PATTERNS = [
        re.compile(r"^\s*Building configuration\.\.\.\s*$", re.IGNORECASE),
        re.compile(r"^\s*Current configuration\s*:\s*\d+\s+bytes\s*$", re.IGNORECASE),
        re.compile(r"^\s*!\s*Last configuration change at\b.*$", re.IGNORECASE),
        re.compile(r"^\s*!\s*NVRAM config last updated at\b.*$", re.IGNORECASE),
        re.compile(r"^\s*!\s*No configuration change since last restart\b.*$", re.IGNORECASE),
        re.compile(r"^\s*ntp\s+clock-period\s+\d+\s*$", re.IGNORECASE),
        re.compile(r"^\s*Using\s+\d+\s+out\s+of\s+\d+\s+bytes\s*$", re.IGNORECASE),
    ]

    @classmethod
    def normalize(cls, text: str) -> str:
        """Normalize line breaks, strip trailing spaces, remove time-varying noise and boundary blanks."""
        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        lines: list[str] = []
        for line in text.split("\n"):
            # Strip trailing whitespace on each line
            clean_line = line.rstrip()

            # Skip time-varying noise lines
            if any(pat.match(clean_line) for pat in cls._TIME_VARYING_PATTERNS):
                continue

            lines.append(clean_line)

        # Remove leading empty lines
        while lines and not lines[0]:
            lines.pop(0)

        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()

        return "\n".join(lines)
