"""Schemas for the AI assistant. Owned by member C; consumed by backend (B).

Design rule: the model's output is UNTRUSTED. Everything it returns must pass
`AssistantExplanation` validation plus the checks in service.py before it can
reach the UI. The assistant never receives credentials and never executes anything.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Must stay in sync with the remediation allowlist in backend/app/remediation (member B/A).
ALLOWED_ACTIONS = ("create_vlan", "configure_access_port")
ActionType = Literal["create_vlan", "configure_access_port"]


class FindingInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rule_id: str = Field(max_length=32)
    title: str = Field(max_length=200)
    severity: Literal["critical", "high", "medium", "low", "info"]
    evidence: list[str] = Field(default_factory=list, max_length=50)
    rationale: str = Field(default="", max_length=2000)
    remediation: str = Field(default="", max_length=2000)


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    finding: FindingInput
    question: Optional[str] = Field(default=None, max_length=500)


class AssistantExplanation(BaseModel):
    """Strict structured output required from the LLM."""
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=600)
    why_it_matters: str = Field(min_length=1, max_length=1200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)
    suggested_action: Optional[ActionType] = None
    suggested_params: dict[str, str] = Field(default_factory=dict)
    confidence: Literal["low", "medium", "high"]
    caveats: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("suggested_params")
    @classmethod
    def _params_small(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 6 or any(len(k) > 32 or len(val) > 64 for k, val in v.items()):
            raise ValueError("suggested_params too large")
        return v


class ExplainResponse(BaseModel):
    provider: str
    explanation: Optional[AssistantExplanation] = None
    rejected_reason: Optional[str] = None
