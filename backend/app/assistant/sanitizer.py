"""Input hygiene for text that will be placed in an LLM prompt, and output hygiene
for text coming back. This reduces risk; it is NOT the security boundary. The boundary
is: AI has no device access, and proposals only become actions via B's allowlist/approval."""
import re

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Phrases typical of prompt-injection / privilege-escalation attempts.
INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any |the )?(previous|prior|above|earlier|your) (instructions|rules)",
    r"(reveal|show|print|repeat|leak) (me )?(your |the )?(system|hidden|initial) (prompt|instructions)",
    r"you are now\b",
    r"act as (an? )?(admin|root|unrestricted|dan)\b",
    r"developer mode",
    r"jailbreak",
    r"\bssh\b.{0,30}\b(into|to)\b",
    r"(run|execute|send|apply|push)\b.{0,40}\b(command|cli|config(uration)?)\b",
    r"configure terminal",
    r"\bconf t\b",
    r"(erase|write erase|reload|delete flash|format flash)",
    r"no (shutdown|enable secret)",
    r"override (the )?(allowlist|approval|rbac|safety|policy)",
    r"bypass (the )?(approval|allowlist|rbac|safety|validation)",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

# Secrets that must never be sent to a third-party LLM.
_SECRET_RE = re.compile(
    r"(?im)^(\s*(?:enable (?:secret|password)(?: \d)?|username \S+ (?:secret|password)(?: \d)?|password(?: \d)?|key(?:-string)?(?: \d)?)\s+)\S+(.*)$"
)
_SNMP = re.compile(r"(?im)^(\s*snmp-server community\s+)(\S+)(.*)$")
_DEFAULT_COMMUNITIES = {"public", "private"}


def clean_text(text: str, max_len: int) -> str:
    text = _CONTROL.sub("", text).replace("\r", "")
    return text[:max_len]


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text))


def mask_secrets(line: str) -> str:
    """Mask credentials. SNMP default community names are kept (they ARE the finding)."""
    def snmp(m: re.Match) -> str:
        name = m.group(2)
        return m.group(0) if name.lower() in _DEFAULT_COMMUNITIES else f"{m.group(1)}<redacted>{m.group(3)}"
    line = _SNMP.sub(snmp, line)
    line = _SECRET_RE.sub(r"\1<redacted>\2", line)
    return line


def sanitize_evidence(lines: list[str]) -> tuple[list[str], int]:
    """Return (safe_lines, number_of_lines_removed_for_injection)."""
    out: list[str] = []
    removed = 0
    for raw in lines:
        line = clean_text(raw, 300)
        if looks_like_injection(line):
            removed += 1
            out.append("[line removed: possible prompt injection in device data]")
        else:
            out.append(mask_secrets(line))
    return out, removed


# Output side ---------------------------------------------------------------
_CLI_LINE = re.compile(
    r"(?im)^\s*(configure terminal|conf t|interface \S+|no \S+|shutdown|write memory|copy running-config|"
    r"reload|erase \S+|username \S+|enable secret|crypto key|vlan \d+|switchport \S+|transport input|ip ssh)\b"
)


def contains_cli(text: str) -> bool:
    """Free-text fields must not carry executable-looking CLI blocks."""
    return bool(_CLI_LINE.search(text))
