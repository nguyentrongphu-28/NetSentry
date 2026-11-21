"""Pydantic schemas for Snapshot endpoints."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class SnapshotOut(BaseModel):
    id: int
    device_id: str
    run_id: int
    created_at: datetime
    content_sha256: str
    size_bytes: int
    line_count: int
    redaction_version: int


class SnapshotDetailOut(SnapshotOut):
    content: str


class DiffLineOut(BaseModel):
    op: str = Field(description="Operation: ' ', '+', or '-'")
    text: str


class DiffHunkOut(BaseModel):
    old_start: int
    new_start: int
    lines: list[DiffLineOut]


class ConfigDiffOut(BaseModel):
    from_run_id: int
    to_run_id: int
    identical: bool
    added: int
    removed: int
    hunks: list[DiffHunkOut]
    truncated: bool
