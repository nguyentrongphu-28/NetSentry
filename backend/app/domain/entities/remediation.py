"""Domain entities for remediation plans and plan events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PlanStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    # Reserved for Remediation D
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    VERIFIED = "VERIFIED"
    VERIFY_FAILED = "VERIFY_FAILED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True, slots=True)
class RemediationPlan:
    id: int
    device_id: str
    run_id: int
    rule_id: str
    template_id: str
    template_version: int
    risk_level: RiskLevel
    commands: tuple[str, ...]
    persist_after_verify: bool
    plan_hash: str
    status: PlanStatus
    proposed_by: str
    proposed_at: datetime
    decided_by: str | None
    decided_at: datetime | None
    decision_reason: str | None
    approved_plan_hash: str | None
    expires_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlanEvent:
    id: int
    plan_id: int
    occurred_at: datetime
    actor: str | None
    event_type: str
    detail: str | None


class ExecutionMode(StrEnum):
    DRY_RUN = "dry_run"
    LIVE = "live"


class ExecutionResult(StrEnum):
    RUNNING = "RUNNING"
    DRY_RUN_OK = "DRY_RUN_OK"
    VERIFIED = "VERIFIED"
    VERIFY_FAILED = "VERIFY_FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    step: str          # PRECHECK_AUDIT | WRITE | POST_AUDIT | SAVE_CONFIG | ROLLBACK | POST_ROLLBACK_AUDIT | DRY_RUN_PREVIEW
    status: str        # STARTED | OK | FAILED | SKIPPED
    at: datetime
    detail: str | None = None  # <= 200 chars, sanitized, no secrets


@dataclass(frozen=True, slots=True)
class RemediationExecution:
    id: int
    plan_id: int
    mode: ExecutionMode
    started_at: datetime
    finished_at: datetime | None
    started_by: str
    result: ExecutionResult
    failure_code: str | None
    changes_sent: bool
    pre_run_id: int | None
    post_run_id: int | None
    rollback_run_id: int | None
    persist_status: str
    needs_manual_attention: bool
    steps: tuple[ExecutionStep, ...]
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    acknowledgement_note: str | None = None
