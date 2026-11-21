from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConfigSnapshot:
    """Metadata for a redacted configuration snapshot."""

    id: int
    device_id: str
    run_id: int
    created_at: datetime
    content_sha256: str
    size_bytes: int
    line_count: int
    redaction_version: int


@dataclass(frozen=True)
class DiffLine:
    """Single line within a diff hunk. op must be ' ', '+', or '-'."""

    op: str
    text: str


@dataclass(frozen=True)
class DiffHunk:
    """A hunk in a unified diff."""

    old_start: int
    new_start: int
    lines: tuple[DiffLine, ...]


@dataclass(frozen=True)
class ConfigDiff:
    """Unified diff between two configuration snapshots."""

    from_run_id: int
    to_run_id: int
    identical: bool
    added: int
    removed: int
    hunks: tuple[DiffHunk, ...]
    truncated: bool
