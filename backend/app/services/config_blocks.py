"""Cisco IOS configuration block splitter.

Converts normalized Cisco IOS configuration into distinct blocks.
"""

from __future__ import annotations

import re

_BANNER_RE = re.compile(r"^banner\s+(\S+)\s+(.)", re.IGNORECASE)


def split_blocks(text: str) -> dict[str, list[str]]:
    """Split normalized Cisco IOS configuration into blocks.

    - Blocks with children: leading unindented line is key, subsequent indented lines are children in exact order.
    - Global lines (unindented without children): grouped into "(global)" block.
    - Multiline banners: treated as a single block keyed by "banner <type>".
    - Comments (!), empty lines, and 'end' are discarded.
    - Duplicate block keys concatenate children without raising error.
    """
    blocks: dict[str, list[str]] = {}
    global_lines: list[str] = []

    lines = text.split("\n")
    i = 0
    n = len(lines)

    while i < n:
        raw_line = lines[i]
        line = raw_line.rstrip()

        # Discard empty, comments, and 'end'
        if not line or line.startswith("!") or line.strip() == "end":
            i += 1
            continue

        # Check for banner delimiter
        banner_match = _BANNER_RE.match(line)
        if banner_match:
            banner_type = banner_match.group(1).lower()
            delim = banner_match.group(2)
            block_key = f"banner {banner_type}"
            banner_lines = [line]

            # Check if delimiter closes on the same line (after opening delim)
            rest_of_line = line[banner_match.end() :]
            if delim in rest_of_line:
                # Banner opens and closes on single line
                blocks.setdefault(block_key, []).extend(banner_lines)
                i += 1
                continue

            # Multiline banner until closing delimiter is found
            i += 1
            while i < n:
                b_line = lines[i].rstrip()
                banner_lines.append(b_line)
                if delim in b_line:
                    break
                i += 1

            blocks.setdefault(block_key, []).extend(banner_lines)
            i += 1
            continue

        # Check indentation: if indented line appears at root unexpectedly, treat as global
        if raw_line.startswith((" ", "\t")):
            global_lines.append(line.strip())
            i += 1
            continue

        # Unindented header line
        header = line.strip()
        # Look ahead for indented child lines
        children: list[str] = []
        j = i + 1
        while j < n:
            next_raw = lines[j]
            next_line = next_raw.rstrip()

            if not next_line:
                j += 1
                continue

            if next_line.startswith("!"):
                j += 1
                continue

            # Child line must start with whitespace
            if next_raw.startswith((" ", "\t")):
                children.append(next_line.strip())
                j += 1
            else:
                # Reached next unindented line
                break

        if children:
            blocks.setdefault(header, []).extend(children)
            i = j
        else:
            global_lines.append(header)
            i += 1

    if global_lines:
        blocks["(global)"] = global_lines

    return blocks
