from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ChangeKind(str, Enum):
    """Classification of how a rule finding transitioned between two audit runs."""

    REGRESSION = "REGRESSION"      # before: PASS (or not present) -> after: FAIL
    FIXED = "FIXED"                # before: FAIL -> after: PASS
    PERSISTING = "PERSISTING"      # FAIL -> FAIL
    UNCHANGED_OK = "UNCHANGED_OK"  # PASS -> PASS
    OTHER = "OTHER"                # all remaining combinations (e.g. UNKNOWN)


@dataclass(frozen=True)
class FindingChange:
    """Individual rule status change between two runs."""

    rule_id: str
    title: str
    before_status: str | None
    after_status: str | None
    before_severity: str | None
    after_severity: str | None
    kind: ChangeKind


@dataclass(frozen=True)
class FindingsDiff:
    """Overall diff of findings between two audit runs."""

    from_run_id: int
    to_run_id: int
    device_id: str
    changes: tuple[FindingChange, ...]
    counts: dict[ChangeKind, int]
    has_previous: bool = True
