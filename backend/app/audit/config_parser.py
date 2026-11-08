# scripts/config_parser.py
"""Parser nhẹ cho running-config Cisco IOS: tách dòng cấp 1 và các khối con."""
import re
from dataclasses import dataclass, field

# Các dòng thay đổi mỗi lần chạy lệnh nhưng không phải thay đổi cấu hình thật
VOLATILE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^Building configuration",
        r"^Current configuration\s*:",
        r"^!\s*Last configuration change",
        r"^!\s*NVRAM config last updated",
        r"^!\s*No configuration change since",
        r"^Using \d+ out of \d+ bytes",
        r"^ntp clock-period",
        r"^end$",
    )
]

_IFACE_PREFIXES = [
    "TenGigabitEthernet", "GigabitEthernet", "FastEthernet", "Port-channel",
    "Ethernet", "Loopback", "Vlan", "Tunnel", "Serial",
]


def normalize_interface_name(name):
    """'Gi0/1' -> 'GigabitEthernet0/1'. Không nhận ra thì trả nguyên văn."""
    name = (name or "").strip()
    m = re.match(r"^([A-Za-z-]+)\s*(\d.*)$", name)
    if not m or len(m.group(1)) < 2:
        return name
    prefix, rest = m.group(1), m.group(2)
    for full in _IFACE_PREFIXES:
        if full.lower().startswith(prefix.lower()):
            return f"{full}{rest}"
    return name


@dataclass
class Block:
    header: str
    children: list = field(default_factory=list)


@dataclass
class ParsedConfig:
    top_lines: list   # mọi dòng cấp 1 (gồm cả header của khối)
    blocks: list      # mọi dòng cấp 1 dưới dạng Block (children có thể rỗng)


def normalize_lines(text):
    """Tách dòng, bỏ dòng trống, dấu '!', và các dòng 'dễ đổi' (timestamp...)."""
    out = []
    for line in (text or "").splitlines():
        line = line.rstrip()
        if not line.strip() or line.strip() == "!":
            continue
        if any(p.match(line.strip()) for p in VOLATILE_PATTERNS):
            continue
        out.append(line)
    return out


def _banner_delimiter(rest):
    return rest[:2] if rest.startswith("^C") else rest[:1]


def parse_config(text):
    top_lines, blocks, current = [], [], None
    lines = normalize_lines(text)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line[0] in (" ", "\t"):
            if current is not None:
                current.children.append(line.strip())
            i += 1
            continue
        current = Block(header=line.strip())
        top_lines.append(current.header)
        blocks.append(current)
        # Banner: bỏ qua phần thân để không bị nhận nhầm là lệnh cấu hình
        m = re.match(r"^banner\s+\S+\s+(\S.*)$", current.header, re.IGNORECASE)
        if m:
            rest = m.group(1)
            delim = _banner_delimiter(rest)
            if delim and rest.count(delim) < 2:
                i += 1
                while i < len(lines) and delim not in lines[i]:
                    i += 1
        i += 1
    return ParsedConfig(top_lines=top_lines, blocks=blocks)


def find_blocks(parsed, header_regex):
    rx = re.compile(header_regex, re.IGNORECASE)
    return [b for b in parsed.blocks if rx.search(b.header)]


def get_interface_block(parsed, interface_name):
    want = normalize_interface_name(interface_name).lower()
    for b in parsed.blocks:
        m = re.match(r"^interface\s+(\S+)$", b.header, re.IGNORECASE)
        if m and normalize_interface_name(m.group(1)).lower() == want:
            return b
    return None
