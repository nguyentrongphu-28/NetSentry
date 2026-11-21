"""Pydantic schemas for baseline and drift API endpoints."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class ApproveBaselineIn(BaseModel):
    snapshot_id: int = Field(..., description="ID of snapshot to set as baseline")
    note: str | None = Field(default=None, max_length=200, description="Optional administrative note")
    confirm_with_failures: bool = Field(
        default=False, description="Must be true if approving snapshot from run with FAIL findings"
    )


class BaselineOut(BaseModel):
    id: int
    device_id: str
    snapshot_id: int
    content_sha256: str
    status: Literal["ACTIVE", "RETIRED"]
    approved_by: str
    approved_at: str
    note: str | None
    fail_count_at_approval: int
    retired_at: str | None = None
    retired_by: str | None = None


class BlockChangeOut(BaseModel):
    key: str
    kind: Literal["ADDED", "REMOVED", "CHANGED"]
    security_relevant: bool
    added_lines: list[str] = Field(default_factory=list)
    removed_lines: list[str] = Field(default_factory=list)
    added_count: int
    removed_count: int


class DriftSummaryOut(BaseModel):
    status: Literal["IN_SYNC", "DRIFTED"]
    added_blocks: int
    removed_blocks: int
    changed_blocks: int
    security_relevant_count: int


class DriftReportOut(BaseModel):
    device_id: str
    baseline_id: int
    run_id: int
    lines_included: bool
    summary: DriftSummaryOut
    blocks: list[BlockChangeOut]
    truncated: bool


class DriftHistoryItemOut(BaseModel):
    run_id: int
    device_id: str
    baseline_id: int
    checked_at: str
    status: Literal["IN_SYNC", "DRIFTED"]
    added_blocks: int
    removed_blocks: int
    changed_blocks: int
    security_relevant_count: int
