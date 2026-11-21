"""Pydantic schemas for remediation API endpoints."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class ProposePlanIn(BaseModel):
    persist_after_verify: bool = Field(
        default=False,
        description="Whether to persist running-config to startup-config after verification passes",
    )


class ApprovePlanIn(BaseModel):
    password: str = Field(..., min_length=1, description="Admin password for step-up authentication")


class RejectPlanIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200, description="Mandatory reason for rejection")


class PlanEventOut(BaseModel):
    id: int
    plan_id: int
    occurred_at: str
    actor: str | None = None
    event_type: str
    detail: str | None = None


class ExpectedVerificationOut(BaseModel):
    rule_id: str
    expected_status: str = "PASS"


class RemediationPlanOut(BaseModel):
    id: int
    device_id: str
    run_id: int
    rule_id: str
    status: Literal[
        "PROPOSED",
        "APPROVED",
        "REJECTED",
        "CANCELLED",
        "EXPIRED",
        "APPLYING",
        "APPLIED",
        "VERIFIED",
        "VERIFY_FAILED",
        "ROLLED_BACK",
        "FAILED",
    ]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    persist_after_verify: bool
    proposed_by: str
    proposed_at: str
    decided_by: str | None = None
    decided_at: str | None = None
    expires_at: str
    plan_hash: str


class RemediationPlanDetailOut(RemediationPlanOut):
    commands: list[str]
    impact: str
    risks: str
    expected_verification: ExpectedVerificationOut
    reversible: bool
    rollback_note: str
    decide_reason: str | None = None
    approved_hash_matches: bool
    timeline: list[PlanEventOut] = Field(default_factory=list)


class RemediationTemplateOut(BaseModel):
    rule_id: str
    version: str
    title: str
    commands: list[str]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    impact: str
    risks: str
    reversible: bool
    rollback_note: str
    rollback_commands: list[str] = Field(default_factory=list)
    platforms: list[str]


class ManualGuidanceOut(BaseModel):
    rule_id: str
    title: str
    remediation_guide: str
    verification_guide: str
    why_not_automated: str


class TemplatesResponseOut(BaseModel):
    templates: list[RemediationTemplateOut]
    manual_guidance: list[ManualGuidanceOut]


# Execution Schemas (Remediation D)

class ApplyPlanIn(BaseModel):
    confirm_device_id: str = Field(..., min_length=1, description="Exact target device_id to prevent misapplied execution")
    password: str = Field(..., min_length=1, description="Admin password for step-up re-authentication")


class ApplyResponseOut(BaseModel):
    plan_id: int
    execution_id: int
    mode: str


class ExecutionStepOut(BaseModel):
    step: str
    status: str
    at: str
    detail: str | None = None


class RemediationExecutionOut(BaseModel):
    id: int
    plan_id: int
    mode: str
    started_at: str
    finished_at: str | None = None
    started_by: str
    result: str
    failure_code: str | None = None
    changes_sent: bool
    pre_run_id: int | None = None
    post_run_id: int | None = None
    rollback_run_id: int | None = None
    persist_status: str
    needs_manual_attention: bool
    steps: list[ExecutionStepOut]
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    acknowledgement_note: str | None = None


class ExecutionStatusOut(BaseModel):
    mode: str
    write_account_configured: bool
    runner_busy: bool


class AttentionPlanOut(BaseModel):
    plan: RemediationPlanOut
    execution: RemediationExecutionOut


class AcknowledgeAttentionIn(BaseModel):
    note: str = Field(..., max_length=200, description="Notes on manual verification/resolution")

