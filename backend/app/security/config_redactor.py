from __future__ import annotations

import hashlib
import hmac
import re

REDACTION_VERSION = 1
_REDACTED_PREFIX = "<REDACTED:"


class ConfigRedactor:
    """Redacts sensitive credentials from configuration text with HMAC-SHA256 fingerprints."""

    def __init__(self, hmac_key: bytes | str = b"netsentry-snapshot-default-key") -> None:
        if isinstance(hmac_key, str):
            self._key = hmac_key.encode("utf-8")
        else:
            self._key = hmac_key

        # Ordered specific IOS patterns
        self._specific_patterns: list[re.Pattern[str]] = [
            # enable password|secret [<type>] <secret>
            re.compile(r"^(?P<pre>\s*enable\s+(?:password|secret)(?:\s+\d+)?\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # username <name> ... password|secret [<type>] <secret>
            re.compile(
                r"^(?P<pre>\s*username\s+\S+(?:(?!\b(?:password|secret)\b).){0,80}\s+(?:password|secret)(?:\s+\d+)?\s+)(?P<sec>\S+)(?P<post>.*)$",
                re.IGNORECASE,
            ),
            # line block / standalone: password [<type>] <secret>
            re.compile(r"^(?P<pre>\s*password(?:\s+\d+)?\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # snmp-server community <secret> [RO|RW] [acl]
            re.compile(r"^(?P<pre>\s*snmp-server\s+community\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # snmp-server host ... version 1|2c <community>
            re.compile(
                r"^(?P<pre>\s*snmp-server\s+host\s+\S+(?:(?!\bversion\b).){0,40}\s+version\s+(?:1|2c)\s+)(?P<sec>\S+)(?P<post>.*)$",
                re.IGNORECASE,
            ),
            # snmp-server host <ip> <community> (without version keyword)
            re.compile(r"^(?P<pre>\s*snmp-server\s+host\s+\S+\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # tacacs-server / radius-server key [<type>] <secret>
            re.compile(r"^(?P<pre>\s*(?:tacacs-server|radius-server)\s+key(?:\s+\d+)?\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # crypto isakmp key <secret> address ...
            re.compile(r"^(?P<pre>\s*crypto\s+isakmp\s+key(?:\s+\d+)?\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # pre-shared-key [<type>] <secret>
            re.compile(r"^(?P<pre>\s*pre-shared-key(?:\s+\d+)?\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # key-chain key-string [<type>] <secret>
            re.compile(r"^(?P<pre>\s*key-string(?:\s+\d+)?\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # key <id> then key [<type>] <secret>
            re.compile(r"^(?P<pre>\s*key\s+[0-9]+\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # ntp authentication-key <n> md5 <secret>
            re.compile(r"^(?P<pre>\s*ntp\s+authentication-key\s+\d+\s+md5\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # ip ospf authentication-key [<type>] <secret>
            re.compile(r"^(?P<pre>\s*ip\s+ospf\s+authentication-key(?:\s+\d+)?\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # ip ospf message-digest-key <n> md5 <secret>
            re.compile(r"^(?P<pre>\s*ip\s+ospf\s+message-digest-key\s+\d+\s+md5\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
            # neighbor <ip> password [<type>] <secret>
            re.compile(r"^(?P<pre>\s*neighbor\s+\S+\s+password(?:\s+\d+)?\s+)(?P<sec>\S+)(?P<post>.*)$", re.IGNORECASE),
        ]

        # SNMPv3 user sub-patterns for auth and priv
        self._snmpv3_auth_pat = re.compile(
            r"(\bauth\s+(?:md5|sha)\s+)(\S+)",
            re.IGNORECASE,
        )
        self._snmpv3_priv_pat = re.compile(
            r"(\bpriv\s+(?:des|3des|aes(?:\s+(?:128|192|256))?)\s+)(\S+)",
            re.IGNORECASE,
        )

        # Keyword pattern for fallback rule
        self._keyword_pat = re.compile(
            r"\b(password|secret|key|community|credential|token)\b",
            re.IGNORECASE,
        )

    def fingerprint(self, secret: str) -> str:
        """Generate 6-character hex HMAC-SHA256 fingerprint."""
        digest = hmac.new(self._key, secret.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{_REDACTED_PREFIX}{digest[:6]}>"

    def redact_line(self, line: str) -> str:
        """Redact credentials in a single line, maintaining line structure and idempotency."""
        if not line:
            return line

        # 1. Handle SNMPv3 multi-credential line specifically
        if "snmp-server user" in line.lower():
            res = line
            # Redact auth
            m_auth = self._snmpv3_auth_pat.search(res)
            if m_auth and not m_auth.group(2).startswith(_REDACTED_PREFIX):
                res = res[:m_auth.start(2)] + self.fingerprint(m_auth.group(2)) + res[m_auth.end(2):]
            # Redact priv
            m_priv = self._snmpv3_priv_pat.search(res)
            if m_priv and not m_priv.group(2).startswith(_REDACTED_PREFIX):
                res = res[:m_priv.start(2)] + self.fingerprint(m_priv.group(2)) + res[m_priv.end(2):]
            return res

        # 2. Match standard specific patterns
        for pat in self._specific_patterns:
            m = pat.match(line)
            if m:
                pre = m.group("pre")
                sec = m.group("sec")
                post = m.group("post")
                if sec.startswith(_REDACTED_PREFIX) and sec.endswith(">"):
                    return line
                return f"{pre}{self.fingerprint(sec)}{post}"

        # 3. Fallback: line contains sensitive keyword but didn't match specific pattern
        # "Mọi dòng chứa từ khóa password|secret|key|community|credential|token mà không khớp mẫu nào ở trên
        # -> che toàn bộ phần sau từ khóa đó"
        kw_m = self._keyword_pat.search(line)
        if kw_m:
            kw_end = kw_m.end()
            after = line[kw_end:]
            if _REDACTED_PREFIX in after:
                return line

            # Check if there is content after the keyword
            stripped_after = after.strip()
            if stripped_after:
                # Keep leading spaces between keyword and secret
                leading_spaces = len(after) - len(after.lstrip())
                spaces = after[:leading_spaces]
                return f"{line[:kw_end]}{spaces}{self.fingerprint(stripped_after)}"

        return line

    def redact(self, raw: str) -> str:
        """Redact entire multiline configuration text."""
        if not raw:
            return raw

        lines = raw.split("\n")
        redacted_lines = [self.redact_line(line) for line in lines]
        return "\n".join(redacted_lines)
