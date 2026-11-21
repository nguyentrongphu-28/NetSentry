"""Drift entities and change kinds."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BlockChangeKind(str, Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    CHANGED = "CHANGED"


@dataclass(frozen=True)
class BlockChange:
    key: str
    kind: BlockChangeKind
    security_relevant: bool
    added_lines: tuple[str, ...]
    removed_lines: tuple[str, ...]
    added_count: int
    removed_count: int


@dataclass(frozen=True)
class DriftSummary:
    status: str
    added_blocks: int
    removed_blocks: int
    changed_blocks: int
    security_relevant_count: int


@dataclass(frozen=True)
class DriftReport:
    device_id: str
    baseline_id: int
    run_id: int
    lines_included: bool
    summary: DriftSummary
    blocks: tuple[BlockChange, ...]
    truncated: bool
