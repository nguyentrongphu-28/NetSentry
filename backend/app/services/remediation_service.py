"""RemediationService managing proposal, approval, rejection, and cancellation of remediation plans."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.finding import FindingStatus
from app.domain.entities.remediation import (
    PlanEvent,
    PlanStatus,
    RemediationPlan,
)
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.domain.errors import (
    ActivePlanExistsError,
    FindingNotFailingError,
    ForbiddenError,
    InvalidTransitionError,
    NotEligibleError,
    PlanExpiredError,
    PlanNotFoundError,
    PlanStaleError,
    RemediationDisabledError,
    SelfApprovalError,
    UserSessionRequiredError,
)
from app.domain.interfaces.audit_repository import AuditRepository
from app.domain.interfaces.device_repository import DeviceRepository
from app.domain.interfaces.remediation_repository import RemediationRepository
from app.domain.interfaces.security_event_repository import SecurityEventRepository
from app.remediation.plan_hash import compute_plan_hash
from app.remediation.state_machine import validate_transition
from app.remediation.templates import build_plan_commands, get_template
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class RemediationService:
    """Core domain service for remediation workflow without device connectivity."""

    def __init__(
        self,
        remediation_repo: RemediationRepository,
        device_repo: DeviceRepository,
        audit_repo: AuditRepository,
        auth_service: AuthService,
        security_event_repo: SecurityEventRepository,
        *,
        enabled: bool = True,
        proposal_ttl_minutes: int = 120,
        approval_ttl_minutes: int = 60,
        max_audit_age_minutes: int = 60,
        require_distinct_approver: bool = True,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = remediation_repo
        self._device_repo = device_repo
        self._audit_repo = audit_repo
        self._auth_service = auth_service
        self._event_repo = security_event_repo
        self._enabled = enabled
        self._proposal_ttl_minutes = proposal_ttl_minutes
        self._approval_ttl_minutes = approval_ttl_minutes
        self._max_audit_age_minutes = max_audit_age_minutes
        self._require_distinct_approver = require_distinct_approver
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _now(self) -> datetime:
        return self._clock()

    def _check_enabled(self) -> None:
        if not self._enabled:
            raise RemediationDisabledError("Remediation planning feature is disabled.")

    def scan_and_expire_stale_plans(self) -> list[RemediationPlan]:
        """Sweep database for expired plans at application startup."""
        if not self._enabled:
            return []
        now = self._now()
        expired = self._repo.expire_stale_plans(now)
        if expired:
            logger.info("Startup sweep expired %d stale remediation plans", len(expired))
        return expired

    def get_plan(self, plan_id: int) -> RemediationPlan:
        """Fetch plan by ID, applying lazy expiration if TTL passed."""
        self._check_enabled()
        plan = self._repo.get_plan(plan_id)
        if plan is None:
            raise PlanNotFoundError(f"Remediation plan #{plan_id} not found.")

        # Lazy expiration
        now = self._now()
        if plan.status in (PlanStatus.PROPOSED, PlanStatus.APPROVED) and now >= plan.expires_at:
            updated = self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=plan.status,
                new_status=PlanStatus.EXPIRED,
                updated_at=now,
            )
            if updated:
                self._repo.add_event(
                    plan_id=plan.id,
                    occurred_at=now,
                    event_type="EXPIRED",
                    actor=None,
                    detail="Plan expired due to TTL timeout",
                )
                refreshed = self._repo.get_plan(plan_id)
                if refreshed:
                    return refreshed
        return plan

    def list_plans_for_device(
        self, device_id: str, status: PlanStatus | None = None, limit: int = 30
    ) -> list[RemediationPlan]:
        """List remediation plans for a device."""
        if not self._enabled:
            return []
        device = self._device_repo.get(device_id)
        if device is None:
            return []
        return self._repo.list_plans_for_device(device_id, status=status, limit=limit)

    def list_events_for_plan(self, plan_id: int) -> list[PlanEvent]:
        """List timeline events for a plan."""
        self._check_enabled()
        # Verify plan exists
        self.get_plan(plan_id)
        return self._repo.list_events(plan_id)

    def propose(
        self,
        run_id: int,
        rule_id: str,
        proposer_username: str,
        proposer_user_id: int | None,
        *,
        persist_after_verify: bool = False,
    ) -> RemediationPlan:
        """Create a new PROPOSED remediation plan from a failing audit finding."""
        self._check_enabled()

        if proposer_user_id is None:
            raise UserSessionRequiredError(
                "An interactive user session is required to propose remediation plans."
            )

        # 1. Fetch audit run
        run_detail = self._audit_repo.get_run(run_id)
        if run_detail is None or run_detail.summary.status != AuditStatus.COMPLETED:
            raise NotEligibleError(f"Audit run #{run_id} is not completed or does not exist.")

        device_id = run_detail.summary.device_id
        device = self._device_repo.get(device_id)
        if device is None:
            raise NotEligibleError(f"Device {device_id!r} not found.")

        # 2. Check rule template and platform eligibility
        tmpl = get_template(rule_id)
        if device.platform not in tmpl.platforms:
            raise NotEligibleError(
                f"Platform {device.platform!r} is not supported by template {tmpl.template_id!r}."
            )

        # 3. Find the finding in the audit run
        target_finding = next((f for f in run_detail.findings if f.rule_id == rule_id), None)
        if target_finding is None:
            raise NotEligibleError(f"Rule {rule_id!r} not evaluated in audit run #{run_id}.")

        if target_finding.status != FindingStatus.FAIL:
            raise FindingNotFailingError(
                f"Finding for rule {rule_id!r} is {target_finding.status.value}, not FAIL."
            )

        # 4. Freshness check: audit must be the latest completed run and <= max_audit_age_minutes
        now = self._now()
        latest = self._audit_repo.latest_run(device_id)
        if latest is None or latest.id != run_id:
            raise PlanStaleError("A newer audit run exists for this device. Please run audit again.")

        audit_finished_at = run_detail.summary.finished_at
        if audit_finished_at.tzinfo is None:
            audit_finished_at = audit_finished_at.replace(tzinfo=timezone.utc)
        if (now - audit_finished_at).total_seconds() > self._max_audit_age_minutes * 60:
            raise PlanStaleError(
                f"Audit run #{run_id} is older than {self._max_audit_age_minutes} minutes. Please run audit again."
            )

        # 5. Build commands and plan hash
        commands = build_plan_commands(tmpl, target_finding)
        plan_hash = compute_plan_hash(
            device_id=device_id,
            rule_id=rule_id,
            template_id=tmpl.template_id,
            template_version=tmpl.version,
            commands=commands,
            persist_after_verify=persist_after_verify,
        )

        expires_at = now + timedelta(minutes=self._proposal_ttl_minutes)

        plan = RemediationPlan(
            id=0,
            device_id=device_id,
            run_id=run_id,
            rule_id=rule_id,
            template_id=tmpl.template_id,
            template_version=tmpl.version,
            risk_level=tmpl.risk_level,
            commands=commands,
            persist_after_verify=persist_after_verify,
            plan_hash=plan_hash,
            status=PlanStatus.PROPOSED,
            proposed_by=proposer_username,
            proposed_at=now,
            decided_by=None,
            decided_at=None,
            decision_reason=None,
            approved_plan_hash=None,
            expires_at=expires_at,
            updated_at=now,
        )

        plan_id = self._repo.create_plan(plan)
        self._repo.add_event(
            plan_id=plan_id,
            occurred_at=now,
            event_type="PROPOSED",
            actor=proposer_username,
            detail="Remediation plan proposed",
        )

        created_plan = self._repo.get_plan(plan_id)
        assert created_plan is not None
        return created_plan

    def approve(
        self,
        plan_id: int,
        approver_username: str,
        approver_user_id: int | None,
        approver_role: Role,
        password: str,
        client_ip: str | None = None,
    ) -> RemediationPlan:
        """Approve a PROPOSED remediation plan with step-up password verification."""
        self._check_enabled()

        if approver_user_id is None:
            raise UserSessionRequiredError(
                "An interactive user session is required to approve remediation plans."
            )

        if approver_role != Role.ADMIN:
            raise ForbiddenError("Only administrators can approve remediation plans.")

        plan = self.get_plan(plan_id)
        now = self._now()

        if plan.status == PlanStatus.EXPIRED:
            raise PlanExpiredError("Remediation plan has expired.")

        if plan.status != PlanStatus.PROPOSED:
            validate_transition(plan.status, PlanStatus.APPROVED)

        # Distinct approver check
        if self._require_distinct_approver and plan.proposed_by == approver_username:
            self._event_repo.add(
                occurred_at=now,
                event_type=SecurityEventType.ACCESS_DENIED,
                actor_username=approver_username,
                client_ip=client_ip,
                target=plan.device_id,
                detail="Self-approval not allowed for remediation plan",
            )
            raise SelfApprovalError(
                "Self-approval is not allowed. A different administrator must approve this plan."
            )

        # Freshness re-check
        latest = self._audit_repo.latest_run(plan.device_id)
        if latest is None or latest.id != plan.run_id:
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.PROPOSED,
                new_status=PlanStatus.EXPIRED,
                updated_at=now,
            )
            self._repo.add_event(
                plan_id=plan.id,
                occurred_at=now,
                event_type="EXPIRED",
                actor=approver_username,
                detail="A newer audit run exists; plan invalidated",
            )
            raise PlanStaleError("A newer audit run exists. Remediation plan is stale.")

        latest_finished_at = latest.finished_at
        if latest_finished_at.tzinfo is None:
            latest_finished_at = latest_finished_at.replace(tzinfo=timezone.utc)
        if (now - latest_finished_at).total_seconds() > self._max_audit_age_minutes * 60:
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.PROPOSED,
                new_status=PlanStatus.EXPIRED,
                updated_at=now,
            )
            self._repo.add_event(
                plan_id=plan.id,
                occurred_at=now,
                event_type="EXPIRED",
                actor=approver_username,
                detail="Source audit is older than maximum age",
            )
            raise PlanStaleError("Source audit run is older than maximum allowed age.")

        # Re-check finding is still FAIL
        run_detail = self._audit_repo.get_run(plan.run_id)
        target_finding = next(
            (f for f in run_detail.findings if f.rule_id == plan.rule_id), None
        ) if run_detail else None
        if target_finding is None or target_finding.status != FindingStatus.FAIL:
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.PROPOSED,
                new_status=PlanStatus.EXPIRED,
                updated_at=now,
            )
            self._repo.add_event(
                plan_id=plan.id,
                occurred_at=now,
                event_type="EXPIRED",
                actor=approver_username,
                detail="Finding is no longer in FAIL status",
            )
            raise PlanStaleError("Finding is no longer in FAIL status.")

        # Recompute hash against active template
        tmpl = get_template(plan.rule_id)
        expected_hash = compute_plan_hash(
            device_id=plan.device_id,
            rule_id=plan.rule_id,
            template_id=tmpl.template_id,
            template_version=tmpl.version,
            commands=plan.commands,
            persist_after_verify=plan.persist_after_verify,
        )
        if expected_hash != plan.plan_hash:
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.PROPOSED,
                new_status=PlanStatus.EXPIRED,
                updated_at=now,
            )
            self._repo.add_event(
                plan_id=plan.id,
                occurred_at=now,
                event_type="EXPIRED",
                actor=approver_username,
                detail="Template version changed since proposal",
            )
            raise PlanStaleError("Plan hash mismatch with current template version.")

        # Step-up authentication
        self._auth_service.verify_password_for_user(approver_user_id, password, client_ip=client_ip)

        # Atomic transition
        new_expires_at = now + timedelta(minutes=self._approval_ttl_minutes)
        updated = self._repo.update_status(
            plan_id=plan.id,
            expected_current_status=PlanStatus.PROPOSED,
            new_status=PlanStatus.APPROVED,
            decided_by=approver_username,
            decided_at=now,
            approved_plan_hash=plan.plan_hash,
            expires_at=new_expires_at,
            updated_at=now,
        )
        if not updated:
            raise InvalidTransitionError("Plan status was concurrently modified.")

        self._repo.add_event(
            plan_id=plan.id,
            occurred_at=now,
            event_type="APPROVED",
            actor=approver_username,
            detail="Plan approved with step-up authentication",
        )

        approved_plan = self._repo.get_plan(plan.id)
        assert approved_plan is not None
        return approved_plan

    def reject(
        self,
        plan_id: int,
        actor_username: str,
        actor_user_id: int | None,
        actor_role: Role,
        reason: str,
        client_ip: str | None = None,
    ) -> RemediationPlan:
        """Reject a PROPOSED remediation plan (admin only)."""
        self._check_enabled()

        if actor_user_id is None:
            raise UserSessionRequiredError(
                "An interactive user session is required to reject remediation plans."
            )

        if actor_role != Role.ADMIN:
            raise ForbiddenError("Only administrators can reject remediation plans.")

        clean_reason = reason.strip()
        if not clean_reason:
            raise ValueError("Rejection reason is required.")
        if len(clean_reason) > 200:
            clean_reason = clean_reason[:200]

        plan = self.get_plan(plan_id)
        now = self._now()

        if plan.status == PlanStatus.EXPIRED:
            raise PlanExpiredError("Remediation plan has expired.")

        if plan.status != PlanStatus.PROPOSED:
            validate_transition(plan.status, PlanStatus.REJECTED)

        updated = self._repo.update_status(
            plan_id=plan.id,
            expected_current_status=PlanStatus.PROPOSED,
            new_status=PlanStatus.REJECTED,
            decided_by=actor_username,
            decided_at=now,
            decision_reason=clean_reason,
            updated_at=now,
        )
        if not updated:
            raise InvalidTransitionError("Plan status was concurrently modified.")

        self._repo.add_event(
            plan_id=plan.id,
            occurred_at=now,
            event_type="REJECTED",
            actor=actor_username,
            detail=clean_reason,
        )

        rejected_plan = self._repo.get_plan(plan.id)
        assert rejected_plan is not None
        return rejected_plan

    def cancel(
        self,
        plan_id: int,
        actor_username: str,
        actor_user_id: int | None,
        actor_role: Role,
        client_ip: str | None = None,
    ) -> RemediationPlan:
        """Cancel a PROPOSED or APPROVED remediation plan."""
        self._check_enabled()

        if actor_user_id is None:
            raise UserSessionRequiredError(
                "An interactive user session is required to cancel remediation plans."
            )

        plan = self.get_plan(plan_id)
        now = self._now()

        if plan.status == PlanStatus.EXPIRED:
            raise PlanExpiredError("Remediation plan has expired.")

        # Cancellation allowed only when PROPOSED or APPROVED
        if plan.status not in (PlanStatus.PROPOSED, PlanStatus.APPROVED):
            validate_transition(plan.status, PlanStatus.CANCELLED)

        # Ownership check: operator can only cancel plans they proposed
        if actor_role != Role.ADMIN and plan.proposed_by != actor_username:
            raise ForbiddenError("Operators can only cancel plans they proposed.")

        updated = self._repo.update_status(
            plan_id=plan.id,
            expected_current_status=plan.status,
            new_status=PlanStatus.CANCELLED,
            updated_at=now,
        )
        if not updated:
            raise InvalidTransitionError("Plan status was concurrently modified.")

        self._repo.add_event(
            plan_id=plan.id,
            occurred_at=now,
            event_type="CANCELLED",
            actor=actor_username,
            detail=f"Plan cancelled by {actor_username}",
        )

        cancelled_plan = self._repo.get_plan(plan.id)
        assert cancelled_plan is not None
        return cancelled_plan
