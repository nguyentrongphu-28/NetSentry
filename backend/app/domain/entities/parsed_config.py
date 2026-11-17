from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigBlock:
    header: str
    children: tuple[str, ...]

    def child_starting_with(self, prefix: str) -> list[str]:
        prefix_lower = prefix.lower()
        return [child for child in self.children if child.lower().startswith(prefix_lower)]

    def has_child(self, prefix: str) -> bool:
        prefix_lower = prefix.lower()
        return any(child.lower().startswith(prefix_lower) for child in self.children)


@dataclass(frozen=True, slots=True)
class ParsedConfig:
    global_lines: tuple[str, ...]
    blocks: tuple[ConfigBlock, ...]

    def global_starting_with(self, prefix: str) -> list[str]:
        prefix_lower = prefix.lower()
        return [line for line in self.global_lines if line.lower().startswith(prefix_lower)]

    def has_global(self, exact: str) -> bool:
        exact_clean = exact.strip().lower()
        return any(line.strip().lower() == exact_clean for line in self.global_lines)

    def blocks_starting_with(self, prefix: str) -> list[ConfigBlock]:
        prefix_lower = prefix.lower()
        return [block for block in self.blocks if block.header.lower().startswith(prefix_lower)]
