"""Pydantic schemas for Compare / Findings Diff endpoints."""

from __future__ import annotations

from pydantic import BaseModel
from app.domain.entities.findings_diff import ChangeKind


class FindingChangeOut(BaseModel):
    rule_id: str
    title: str
    before_status: str | None = None
    after_status: str | None = None
    before_severity: str | None = None
    after_severity: str | None = None
    kind: ChangeKind


class CompareOut(BaseModel):
    from_run_id: int | None = None
    to_run_id: int
    device_id: str
    has_previous: bool
    changes: list[FindingChangeOut]
    counts: dict[str, int]
