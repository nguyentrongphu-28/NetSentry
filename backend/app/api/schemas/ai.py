"""Pydantic schemas for AI explanation endpoints (Spec 7, 8.7)."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PriorityItemOut(BaseModel):
    rule_id: str
    reason: str


class RiskNoteOut(BaseModel):
    rule_id: str
    warning: str


class AiStatusOut(BaseModel):
    enabled: bool
    reachable: bool
    model: str


class AiExplanationOut(BaseModel):
    run_id: int
    created_at: datetime
    model: str
    prompt_version: int
    input_sha256: str
    summary: str
    priorities: list[PriorityItemOut]
    risks: list[RiskNoteOut]
    generated_by_ai: bool = True
