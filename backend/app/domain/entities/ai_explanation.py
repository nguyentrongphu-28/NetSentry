from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PriorityItem:
    rule_id: str
    reason: str


@dataclass(frozen=True)
class RiskNote:
    rule_id: str
    warning: str


@dataclass(frozen=True)
class AiExplanation:
    run_id: int
    created_at: datetime
    model: str
    prompt_version: int
    input_sha256: str
    summary: str
    priorities: tuple[PriorityItem, ...]
    risks: tuple[RiskNote, ...]
    generated_by_ai: bool = True
