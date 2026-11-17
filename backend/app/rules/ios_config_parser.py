from __future__ import annotations

import re

from app.domain.entities.parsed_config import ConfigBlock, ParsedConfig
from app.domain.interfaces.config_parser import ConfigParser

_BANNER_PATTERN = re.compile(r"^banner\s+\S+\s+(\S.*)$", re.IGNORECASE)


class IosConfigParser(ConfigParser):
    """Parser for Cisco IOS configuration text into structured ParsedConfig."""

    def parse(self, text: str) -> ParsedConfig:
        if not isinstance(text, str) or not text.strip():
            return ParsedConfig(global_lines=(), blocks=())

        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")

        global_lines: list[str] = []
        blocks: list[ConfigBlock] = []

        in_banner = False
        banner_delim = ""

        pending_header: str | None = None
        pending_children: list[str] = []

        def commit_pending() -> None:
            nonlocal pending_header, pending_children
            if pending_header is not None:
                if pending_children:
                    blocks.append(
                        ConfigBlock(
                            header=pending_header,
                            children=tuple(pending_children),
                        )
                    )
                else:
                    global_lines.append(pending_header)
                pending_header = None
                pending_children = []

        for raw_line in lines:
            if in_banner:
                if banner_delim and banner_delim in raw_line:
                    in_banner = False
                    banner_delim = ""
                continue

            stripped = raw_line.strip()
            if not stripped:
                continue

            if stripped.startswith("!"):
                continue

            stripped_lower = stripped.lower()
            if stripped_lower == "end":
                continue
            if stripped_lower.startswith("building configuration..."):
                continue
            if stripped_lower.startswith("current configuration :"):
                continue
            if (
                stripped_lower.startswith("using ")
                and "out of" in stripped_lower
                and "bytes" in stripped_lower
            ):
                continue

            banner_match = _BANNER_PATTERN.match(stripped)
            if banner_match:
                rest = banner_match.group(1)
                if rest.startswith("^") and len(rest) >= 2 and rest[1].isalpha():
                    delim = rest[:2]
                    content_after = rest[2:]
                else:
                    delim = rest[0]
                    content_after = rest[1:]

                if delim in content_after:
                    # Single-line banner, closing delimiter is on the same line
                    continue

                in_banner = True
                banner_delim = delim
                continue

            is_indented = raw_line[0] in (" ", "\t")
            if not is_indented:
                commit_pending()
                pending_header = stripped
            else:
                if pending_header is not None:
                    pending_children.append(stripped)
                else:
                    global_lines.append(stripped)

        commit_pending()

        return ParsedConfig(
            global_lines=tuple(global_lines),
            blocks=tuple(blocks),
        )
