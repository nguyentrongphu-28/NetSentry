"""Abstract interface for remediation plans and events storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.remediation import (
    PlanEvent,
    PlanStatus,
    RemediationExecution,
    RemediationPlan,
)


class RemediationRepository(ABC):
    """Abstract contract for persisting and querying remediation plans and events."""

    @abstractmethod
    def create_plan(self, plan: RemediationPlan) -> int:
        """Persist a new proposed remediation plan and return its generated ID.

        Raises ActivePlanExistsError if an active plan already exists for (device_id, rule_id).
        """
        raise NotImplementedError

    @abstractmethod
    def get_plan(self, plan_id: int) -> RemediationPlan | None:
        """Return RemediationPlan by its ID, or None if not found."""
        raise NotImplementedError

    @abstractmethod
    def list_plans_for_device(
        self, device_id: str, status: PlanStatus | None = None, limit: int = 30
    ) -> list[RemediationPlan]:
        """List plans for a device, ordered by proposed_at DESC, limit clamped to [1, 200]."""
        raise NotImplementedError

    @abstractmethod
    def get_active_plan(self, device_id: str, rule_id: str) -> RemediationPlan | None:
        """Return the active plan (PROPOSED, APPROVED, or APPLYING) for (device_id, rule_id), if any."""
        raise NotImplementedError

    @abstractmethod
    def update_status(
        self,
        plan_id: int,
        expected_current_status: PlanStatus,
        new_status: PlanStatus,
        *,
        decided_by: str | None = None,
        decided_at: datetime | None = None,
        decision_reason: str | None = None,
        approved_plan_hash: str | None = None,
        expires_at: datetime | None = None,
        updated_at: datetime,
    ) -> bool:
        """Atomically transition plan from expected_current_status to new_status.

        Returns True if transition succeeded (1 row updated), False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def expire_stale_plans(self, now: datetime) -> list[RemediationPlan]:
        """Find all active plans where expires_at <= now, transition them to EXPIRED atomically,

        and return the list of transitioned plans.
        """
        raise NotImplementedError

    @abstractmethod
    def add_event(
        self,
        plan_id: int,
        occurred_at: datetime,
        event_type: str,
        actor: str | None = None,
        detail: str | None = None,
    ) -> int:
        """Append an event to the remediation plan's timeline. Returns event ID."""
        raise NotImplementedError

    @abstractmethod
    def list_events(self, plan_id: int) -> list[PlanEvent]:
        """Return all events for a plan ordered by id ASC."""
        raise NotImplementedError

    @abstractmethod
    def acquire_device_for_applying(
        self,
        plan_id: int,
        device_id: str,
        updated_at: datetime,
    ) -> bool:
        """Atomically transition plan from APPROVED to APPLYING with device lock.

        Only succeeds if plan is in APPROVED and no other plan for device_id is in APPLYING or APPLIED.
        Returns True if transition succeeded, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def is_device_busy(self, device_id: str) -> bool:
        """Return True if any plan for device_id is currently in APPLYING or APPLIED status."""
        raise NotImplementedError

    @abstractmethod
    def create_execution(self, execution: RemediationExecution) -> int:
        """Persist a new execution record and return its ID."""
        raise NotImplementedError

    @abstractmethod
    def update_execution(self, execution: RemediationExecution) -> None:
        """Update an existing execution record."""
        raise NotImplementedError

    @abstractmethod
    def get_execution(self, execution_id: int) -> RemediationExecution | None:
        """Return execution by ID, or None."""
        raise NotImplementedError

    @abstractmethod
    def list_executions_for_plan(self, plan_id: int) -> list[RemediationExecution]:
        """List all execution records for a plan, ordered by started_at DESC."""
        raise NotImplementedError

    @abstractmethod
    def get_latest_execution_for_plan(self, plan_id: int) -> RemediationExecution | None:
        """Return the latest execution record for a plan, or None."""
        raise NotImplementedError

    @abstractmethod
    def list_attention_executions(self) -> list[tuple[RemediationPlan, RemediationExecution]]:
        """Return all plans with unacknowledged executions needing manual attention."""
        raise NotImplementedError

    @abstractmethod
    def acknowledge_attention(
        self,
        plan_id: int,
        actor: str,
        note: str,
        acknowledged_at: datetime,
    ) -> bool:
        """Record acknowledgement for manual attention executions of a plan."""
        raise NotImplementedError

    @abstractmethod
    def get_stale_running_executions(self, cutoff: datetime) -> list[RemediationExecution]:
        """Return RUNNING executions started before cutoff."""
        raise NotImplementedError

