"""Remediation executor and background execution runner for Remediation D."""

from __future__ import annotations

import concurrent.futures
from dataclasses import replace
from datetime import datetime, timezone
import logging
from typing import Callable

from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.findings_diff import ChangeKind
from app.domain.entities.remediation import (
    ExecutionMode,
    ExecutionResult,
    ExecutionStep,
    PlanStatus,
    RemediationExecution,
    RemediationPlan,
)
from app.domain.entities.security_event import SecurityEventType
from app.domain.errors import (
    CommandNotAllowedError,
    WriteAuthFailedError,
    WriteConnectionError,
    WriteRejectedError,
)
from app.domain.interfaces.config_writer import ConfigWriterFactory
from app.domain.interfaces.device_repository import DeviceRepository
from app.domain.interfaces.remediation_repository import RemediationRepository
from app.domain.interfaces.security_event_repository import SecurityEventRepository
from app.remediation.templates import get_template
from app.services.audit_run_service import AuditRunService
from app.services.diff_service import DiffService

logger = logging.getLogger(__name__)


class ExecutionRunner:
    """Single-worker background executor ensuring maximum of one active execution cluster-wide."""

    def __init__(self) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._active_future: concurrent.futures.Future[None] | None = None

    def submit(self, fn: Callable[..., None], *args: object, **kwargs: object) -> None:
        self._active_future = self._executor.submit(fn, *args, **kwargs)

    def is_busy(self) -> bool:
        return self._active_future is not None and self._active_future.running()

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait)


class RemediationExecutor:
    """Orchestrates safe precheck, write, verification, save/rollback, and crash recovery."""

    def __init__(
        self,
        remediation_repo: RemediationRepository,
        writer_factory: ConfigWriterFactory,
        audit_run_service: AuditRunService,
        diff_service: DiffService,
        device_repo: DeviceRepository,
        *,
        security_event_repo: SecurityEventRepository | None = None,
        clock: Callable[[], datetime] | None = None,
        runner: ExecutionRunner | None = None,
    ) -> None:
        self._repo = remediation_repo
        self._writer_factory = writer_factory
        self._audit_service = audit_run_service
        self._diff_service = diff_service
        self._device_repo = device_repo
        self._security_repo = security_event_repo
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._runner = runner or ExecutionRunner()

    @property
    def runner(self) -> ExecutionRunner:
        return self._runner

    def _now(self) -> datetime:
        return self._clock()

    def _log_security_event(
        self,
        event_type: SecurityEventType,
        actor: str,
        target: str,
        detail: str,
    ) -> None:
        if self._security_repo is not None:
            self._security_repo.add(
                occurred_at=self._now(),
                event_type=event_type,
                actor_username=actor,
                client_ip=None,
                target=target,
                detail=detail[:200],
            )

    def _add_step(
        self,
        execution: RemediationExecution,
        step_name: str,
        status: str,
        detail: str | None = None,
    ) -> RemediationExecution:
        now = self._now()
        clean_detail = detail[:200] if detail else None
        new_step = ExecutionStep(step=step_name, status=status, at=now, detail=clean_detail)
        updated = replace(execution, steps=(*execution.steps, new_step))
        self._repo.update_execution(updated)
        return updated

    def execute_async(self, plan_id: int, execution_id: int) -> None:
        """Enqueue background execution task."""
        self._runner.submit(self._run_job, plan_id, execution_id)

    def _run_job(self, plan_id: int, execution_id: int) -> None:
        """Worker thread entrypoint wrapped in catch-all to prevent unhandled lockouts."""
        execution = self._repo.get_execution(execution_id)
        plan = self._repo.get_plan(plan_id)
        if execution is None or plan is None:
            logger.error("Execution %d or Plan %d not found for runner", execution_id, plan_id)
            return

        try:
            if execution.mode == ExecutionMode.DRY_RUN:
                self._execute_dry_run(plan, execution)
            else:
                self._execute_live(plan, execution)
        except Exception as exc:
            logger.exception("Unexpected exception in remediation executor for plan #%d: %s", plan_id, exc)
            now = self._now()
            # Failsafe: transition plan out of APPLYING/APPLIED to FAILED
            curr_plan = self._repo.get_plan(plan_id)
            if curr_plan and curr_plan.status in (PlanStatus.APPLYING, PlanStatus.APPLIED):
                self._repo.update_status(
                    plan_id=plan_id,
                    expected_current_status=curr_plan.status,
                    new_status=PlanStatus.FAILED,
                    updated_at=now,
                )
            # Mark execution FAILED with needs_manual_attention
            curr_exec = self._repo.get_execution(execution_id)
            if curr_exec and curr_exec.result == ExecutionResult.RUNNING:
                fail_exec = replace(
                    curr_exec,
                    finished_at=now,
                    result=ExecutionResult.FAILED,
                    failure_code="UNEXPECTED_ERROR",
                    needs_manual_attention=True,
                )
                self._repo.update_execution(fail_exec)
                self._repo.add_event(
                    plan_id=plan_id,
                    occurred_at=now,
                    event_type="FAILED",
                    actor=curr_exec.started_by,
                    detail=f"Execution error: {type(exc).__name__}",
                )
                self._log_security_event(
                    SecurityEventType.REMEDIATION_FAILED,
                    curr_exec.started_by,
                    plan.device_id,
                    f"Unexpected error in executor for plan #{plan.id}",
                )

    def _execute_dry_run(
        self,
        plan: RemediationPlan,
        execution: RemediationExecution,
    ) -> None:
        """Dry-run: runs real read precheck audit, previews commands, does not touch writer."""
        now = self._now()
        # 1. PRECHECK_AUDIT
        execution = self._add_step(execution, "PRECHECK_AUDIT", "STARTED")
        try:
            pre_run = self._audit_service.run_audit(plan.device_id)
        except Exception as exc:
            now = self._now()
            execution = self._add_step(execution, "PRECHECK_AUDIT", "FAILED", f"Audit failed: {type(exc).__name__}")
            failed_exec = replace(
                execution,
                finished_at=now,
                result=ExecutionResult.FAILED,
                failure_code="PRECHECK_FAILED",
                needs_manual_attention=False,
            )
            self._repo.update_execution(failed_exec)
            self._repo.add_event(plan.id, now, "FAILED", execution.started_by, "Dry-run precheck failed")
            return

        pre_finding = next((f for f in pre_run.findings if f.rule_id == plan.rule_id), None)
        if pre_run.summary.status != AuditStatus.COMPLETED or pre_finding is None or pre_finding.status.value != "FAIL":
            now = self._now()
            detail = "Finding is not in FAIL status" if pre_finding and pre_finding.status.value != "FAIL" else "Audit incomplete"
            execution = self._add_step(execution, "PRECHECK_AUDIT", "FAILED", detail)
            failed_exec = replace(
                execution,
                pre_run_id=pre_run.summary.id,
                finished_at=now,
                result=ExecutionResult.FAILED,
                failure_code="PRECHECK_NOT_FAILING" if pre_finding and pre_finding.status.value != "FAIL" else "PRECHECK_FAILED",
                needs_manual_attention=False,
            )
            self._repo.update_execution(failed_exec)
            self._repo.add_event(plan.id, now, "FAILED", execution.started_by, f"Dry-run precheck: {detail}")
            return

        execution = self._add_step(execution, "PRECHECK_AUDIT", "OK", f"Audit #{pre_run.summary.id} confirmed FAIL")
        execution = replace(execution, pre_run_id=pre_run.summary.id)
        self._repo.update_execution(execution)

        # 2. DRY_RUN_PREVIEW
        preview_detail = f"Commands to send: {', '.join(plan.commands)}"
        execution = self._add_step(execution, "DRY_RUN_PREVIEW", "OK", preview_detail)

        # Dry-run finishes successfully with DRY_RUN_OK; plan stays in APPROVED
        now = self._now()
        completed_exec = replace(
            execution,
            finished_at=now,
            result=ExecutionResult.DRY_RUN_OK,
            needs_manual_attention=False,
        )
        self._repo.update_execution(completed_exec)
        self._repo.add_event(plan.id, now, "DRY_RUN", execution.started_by, "Dry-run completed successfully")
        self._log_security_event(
            SecurityEventType.REMEDIATION_DRY_RUN,
            execution.started_by,
            plan.device_id,
            f"Dry run OK for plan #{plan.id} ({plan.rule_id})",
        )

    def _execute_live(
        self,
        plan: RemediationPlan,
        execution: RemediationExecution,
    ) -> None:
        """Full live execution lifecycle."""
        template = get_template(plan.rule_id)
        device = self._device_repo.get(plan.device_id)
        if device is None:
            raise RuntimeError(f"Device {plan.device_id} not found")

        # -------------------------------------------------------------
        # Step 1: PRECHECK_AUDIT (read)
        # -------------------------------------------------------------
        execution = self._add_step(execution, "PRECHECK_AUDIT", "STARTED")
        try:
            pre_run = self._audit_service.run_audit(plan.device_id)
        except Exception as exc:
            now = self._now()
            execution = self._add_step(execution, "PRECHECK_AUDIT", "FAILED", f"Precheck error: {type(exc).__name__}")
            self._fail_execution(
                plan=plan,
                execution=execution,
                failure_code="PRECHECK_FAILED",
                needs_attention=False,
                changes_sent=False,
                detail=f"Precheck audit failed: {type(exc).__name__}",
            )
            return

        pre_finding = next((f for f in pre_run.findings if f.rule_id == plan.rule_id), None)
        if pre_run.summary.status != AuditStatus.COMPLETED or pre_finding is None or pre_finding.status.value != "FAIL":
            now = self._now()
            detail = "Finding is not in FAIL status" if pre_finding and pre_finding.status.value != "FAIL" else "Audit incomplete"
            execution = self._add_step(execution, "PRECHECK_AUDIT", "FAILED", detail)
            self._fail_execution(
                plan=plan,
                execution=replace(execution, pre_run_id=pre_run.summary.id),
                failure_code="PRECHECK_NOT_FAILING" if pre_finding and pre_finding.status.value != "FAIL" else "PRECHECK_FAILED",
                needs_attention=False,
                changes_sent=False,
                detail=f"Precheck aborted: {detail}",
            )
            return

        execution = self._add_step(execution, "PRECHECK_AUDIT", "OK", f"Audit #{pre_run.summary.id} confirmed FAIL")
        execution = replace(execution, pre_run_id=pre_run.summary.id)
        self._repo.update_execution(execution)

        # -------------------------------------------------------------
        # Step 2: WRITE
        # -------------------------------------------------------------
        execution = self._add_step(execution, "WRITE", "STARTED")
        writer = self._writer_factory.create_writer(
            device_id=device.device_id,
            host=device.host,
            port=device.port,
            platform=device.platform,
        )

        try:
            with writer:
                write_result = writer.apply(plan.commands, is_rollback=False)
        except WriteAuthFailedError as auth_err:
            execution = self._add_step(execution, "WRITE", "FAILED", "Write channel authentication failed")
            self._fail_execution(
                plan=plan,
                execution=execution,
                failure_code="WRITE_AUTH_FAILED",
                needs_attention=False,
                changes_sent=False,
                detail="Write channel auth failed",
            )
            return
        except WriteRejectedError as rej_err:
            execution = self._add_step(execution, "WRITE", "FAILED", str(rej_err))
            self._fail_execution(
                plan=plan,
                execution=execution,
                failure_code="WRITE_REJECTED",
                needs_attention=False,
                changes_sent=False,
                detail=str(rej_err),
            )
            return
        except (WriteConnectionError, Exception) as conn_err:
            execution = self._add_step(execution, "WRITE", "FAILED", f"Write connection error: {type(conn_err).__name__}")
            # Uncertain device state -> needs_manual_attention=True
            self._fail_execution(
                plan=plan,
                execution=execution,
                failure_code="WRITE_CONNECTION_FAILED",
                needs_attention=True,
                changes_sent=False,
                detail=f"Write connection lost: {type(conn_err).__name__}",
            )
            return

        # Commands accepted by device! Atomically transition APPLYING -> APPLIED
        now = self._now()
        execution = self._add_step(execution, "WRITE", "OK", f"{len(plan.commands)} commands accepted by device")
        execution = replace(execution, changes_sent=True)
        self._repo.update_execution(execution)

        applied_ok = self._repo.update_status(
            plan_id=plan.id,
            expected_current_status=PlanStatus.APPLYING,
            new_status=PlanStatus.APPLIED,
            updated_at=now,
        )
        if not applied_ok:
            logger.error("Failed transition APPLYING -> APPLIED for plan #%d", plan.id)

        # -------------------------------------------------------------
        # Step 3: POST_AUDIT (verification)
        # -------------------------------------------------------------
        execution = self._add_step(execution, "POST_AUDIT", "STARTED")
        try:
            post_run = self._audit_service.run_audit(plan.device_id)
        except Exception as exc:
            now = self._now()
            execution = self._add_step(execution, "POST_AUDIT", "FAILED", f"Post-audit failed: {type(exc).__name__}")
            # Verification audit unavailable! Try best-effort rollback if reversible, but mark FAILED with POST_AUDIT_UNAVAILABLE
            self._handle_post_audit_unavailable(plan, template, device, execution, f"Post-audit unavailable: {type(exc).__name__}")
            return

        execution = replace(execution, post_run_id=post_run.summary.id)
        self._repo.update_execution(execution)

        if post_run.summary.status != AuditStatus.COMPLETED:
            execution = self._add_step(execution, "POST_AUDIT", "FAILED", "Post-audit did not complete")
            self._handle_post_audit_unavailable(plan, template, device, execution, "Post-audit run did not complete")
            return

        # Check target rule status and check for regression
        post_finding = next((f for f in post_run.findings if f.rule_id == template.expected_verification[0]), None)
        rule_passed = post_finding is not None and post_finding.status.value == template.expected_verification[1]

        diff = self._diff_service.findings_diff(pre_run, post_run)
        has_regression = any(c.kind == ChangeKind.REGRESSION for c in diff.changes)

        if rule_passed and not has_regression:
            # ---------------------------------------------------------
            # Step 4: Verification Success! Transition to VERIFIED
            # ---------------------------------------------------------
            execution = self._add_step(execution, "POST_AUDIT", "OK", f"Rule {plan.rule_id} verified PASS; no regression")
            now = self._now()
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.APPLIED,
                new_status=PlanStatus.VERIFIED,
                updated_at=now,
            )

            # SAVE_CONFIG if persist_after_verify
            persist_status = "NOT_REQUESTED"
            if plan.persist_after_verify:
                execution = self._add_step(execution, "SAVE_CONFIG", "STARTED")
                try:
                    with writer:
                        writer.save_config()
                    persist_status = "SAVED"
                    execution = self._add_step(execution, "SAVE_CONFIG", "OK", "write memory successful")
                except Exception as save_err:
                    persist_status = "FAILED"
                    execution = self._add_step(execution, "SAVE_CONFIG", "FAILED", f"write memory failed: {save_err}")

            now = self._now()
            verified_exec = replace(
                execution,
                finished_at=now,
                result=ExecutionResult.VERIFIED,
                persist_status=persist_status,
                needs_manual_attention=False,
            )
            self._repo.update_execution(verified_exec)
            self._repo.add_event(plan.id, now, "VERIFIED", execution.started_by, f"Audit #{post_run.summary.id} verified PASS")
            self._log_security_event(
                SecurityEventType.REMEDIATION_VERIFIED,
                execution.started_by,
                plan.device_id,
                f"Remediation plan #{plan.id} verified for rule {plan.rule_id}",
            )
            return

        # -------------------------------------------------------------
        # Step 5: Verification Failed!
        # -------------------------------------------------------------
        fail_reason = "Rule did not pass verification" if not rule_passed else "Regression detected on other rules"
        execution = self._add_step(execution, "POST_AUDIT", "FAILED", fail_reason)

        if not template.reversible:
            # Irreversible template (e.g. NET-004) -> VERIFY_FAILED, do not roll back
            now = self._now()
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.APPLIED,
                new_status=PlanStatus.VERIFY_FAILED,
                updated_at=now,
            )
            vfail_exec = replace(
                execution,
                finished_at=now,
                result=ExecutionResult.VERIFY_FAILED,
                needs_manual_attention=True,
                failure_code="VERIFY_FAILED",
            )
            self._repo.update_execution(vfail_exec)
            self._repo.add_event(plan.id, now, "VERIFY_FAILED", execution.started_by, f"Verification failed (irreversible): {fail_reason}")
            self._log_security_event(
                SecurityEventType.REMEDIATION_FAILED,
                execution.started_by,
                plan.device_id,
                f"Remediation plan #{plan.id} VERIFY_FAILED (irreversible)",
            )
            return

        # Template is reversible -> execute ROLLBACK
        self._perform_rollback(plan, template, device, pre_run, execution, fail_reason)

    def _perform_rollback(
        self,
        plan: RemediationPlan,
        template: Any,
        device: Any,
        pre_run: Any,
        execution: RemediationExecution,
        original_fail_reason: str,
    ) -> None:
        """Apply rollback commands and perform POST_ROLLBACK_AUDIT."""
        execution = self._add_step(execution, "ROLLBACK", "STARTED", f"Reverting due to: {original_fail_reason}")
        writer = self._writer_factory.create_writer(
            device_id=device.device_id,
            host=device.host,
            port=device.port,
            platform=device.platform,
        )

        try:
            with writer:
                writer.apply(template.rollback_commands, is_rollback=True)
            execution = self._add_step(execution, "ROLLBACK", "OK", "Rollback commands applied")
        except Exception as rb_err:
            execution = self._add_step(execution, "ROLLBACK", "FAILED", f"Rollback failed: {rb_err}")
            now = self._now()
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.APPLIED,
                new_status=PlanStatus.FAILED,
                updated_at=now,
            )
            rb_fail_exec = replace(
                execution,
                finished_at=now,
                result=ExecutionResult.FAILED,
                failure_code="ROLLBACK_FAILED",
                needs_manual_attention=True,
            )
            self._repo.update_execution(rb_fail_exec)
            self._repo.add_event(plan.id, now, "FAILED", execution.started_by, f"Rollback failed: {rb_err}")
            self._log_security_event(
                SecurityEventType.REMEDIATION_FAILED,
                execution.started_by,
                plan.device_id,
                f"Rollback failed for plan #{plan.id}",
            )
            return

        # POST_ROLLBACK_AUDIT
        execution = self._add_step(execution, "POST_ROLLBACK_AUDIT", "STARTED")
        try:
            rb_run = self._audit_service.run_audit(plan.device_id)
        except Exception as exc:
            now = self._now()
            execution = self._add_step(execution, "POST_ROLLBACK_AUDIT", "FAILED", f"Audit failed: {type(exc).__name__}")
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.APPLIED,
                new_status=PlanStatus.FAILED,
                updated_at=now,
            )
            unver_exec = replace(
                execution,
                finished_at=now,
                result=ExecutionResult.FAILED,
                failure_code="ROLLBACK_UNVERIFIED",
                needs_manual_attention=True,
            )
            self._repo.update_execution(unver_exec)
            self._repo.add_event(plan.id, now, "FAILED", execution.started_by, "Rollback audit failed")
            return

        execution = replace(execution, rollback_run_id=rb_run.summary.id)
        self._repo.update_execution(execution)

        # Confirm state reverted to pre_run (no regression relative to pre_run)
        rb_diff = self._diff_service.findings_diff(pre_run, rb_run)
        has_rb_regression = any(c.kind == ChangeKind.REGRESSION for c in rb_diff.changes)

        if rb_run.summary.status == AuditStatus.COMPLETED and not has_rb_regression:
            execution = self._add_step(execution, "POST_ROLLBACK_AUDIT", "OK", "Device returned to pre-remediation baseline")
            now = self._now()
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.APPLIED,
                new_status=PlanStatus.ROLLED_BACK,
                updated_at=now,
            )
            rb_done_exec = replace(
                execution,
                finished_at=now,
                result=ExecutionResult.ROLLED_BACK,
                needs_manual_attention=False,
            )
            self._repo.update_execution(rb_done_exec)
            self._repo.add_event(plan.id, now, "ROLLED_BACK", execution.started_by, "Verification failed; reverted successfully")
            self._log_security_event(
                SecurityEventType.REMEDIATION_ROLLED_BACK,
                execution.started_by,
                plan.device_id,
                f"Remediation plan #{plan.id} rolled back successfully",
            )
        else:
            execution = self._add_step(execution, "POST_ROLLBACK_AUDIT", "FAILED", "Device state after rollback does not match pre-audit")
            now = self._now()
            self._repo.update_status(
                plan_id=plan.id,
                expected_current_status=PlanStatus.APPLIED,
                new_status=PlanStatus.FAILED,
                updated_at=now,
            )
            unver_exec = replace(
                execution,
                finished_at=now,
                result=ExecutionResult.FAILED,
                failure_code="ROLLBACK_UNVERIFIED",
                needs_manual_attention=True,
            )
            self._repo.update_execution(unver_exec)
            self._repo.add_event(plan.id, now, "FAILED", execution.started_by, "Rollback unverified")
            self._log_security_event(
                SecurityEventType.REMEDIATION_FAILED,
                execution.started_by,
                plan.device_id,
                f"Rollback unverified for plan #{plan.id}",
            )

    def _handle_post_audit_unavailable(
        self,
        plan: RemediationPlan,
        template: Any,
        device: Any,
        execution: RemediationExecution,
        reason: str,
    ) -> None:
        """Best effort rollback when post audit cannot connect, but always mark FAILED + needs_attention."""
        if template.reversible:
            execution = self._add_step(execution, "ROLLBACK", "STARTED", "Best-effort rollback because post-audit is unavailable")
            try:
                writer = self._writer_factory.create_writer(
                    device_id=device.device_id,
                    host=device.host,
                    port=device.port,
                    platform=device.platform,
                )
                with writer:
                    writer.apply(template.rollback_commands, is_rollback=True)
                execution = self._add_step(execution, "ROLLBACK", "OK", "Best-effort rollback applied")
            except Exception as exc:
                execution = self._add_step(execution, "ROLLBACK", "FAILED", f"Best-effort rollback failed: {exc}")

        now = self._now()
        self._repo.update_status(
            plan_id=plan.id,
            expected_current_status=PlanStatus.APPLIED,
            new_status=PlanStatus.FAILED,
            updated_at=now,
        )
        fail_exec = replace(
            execution,
            finished_at=now,
            result=ExecutionResult.FAILED,
            failure_code="POST_AUDIT_UNAVAILABLE",
            needs_manual_attention=True,
        )
        self._repo.update_execution(fail_exec)
        self._repo.add_event(plan.id, now, "FAILED", execution.started_by, f"Post-audit unavailable: {reason}")
        self._log_security_event(
            SecurityEventType.REMEDIATION_FAILED,
            execution.started_by,
            plan.device_id,
            f"Plan #{plan.id} failed: post audit unavailable",
        )

    def _fail_execution(
        self,
        plan: RemediationPlan,
        execution: RemediationExecution,
        failure_code: str,
        needs_attention: bool,
        changes_sent: bool,
        detail: str,
    ) -> None:
        now = self._now()
        # Transition plan from APPLYING to FAILED
        self._repo.update_status(
            plan_id=plan.id,
            expected_current_status=PlanStatus.APPLYING,
            new_status=PlanStatus.FAILED,
            updated_at=now,
        )
        fail_exec = replace(
            execution,
            finished_at=now,
            result=ExecutionResult.FAILED,
            failure_code=failure_code,
            changes_sent=changes_sent,
            needs_manual_attention=needs_attention,
        )
        self._repo.update_execution(fail_exec)
        self._repo.add_event(plan.id, now, "FAILED", execution.started_by, detail)
        self._log_security_event(
            SecurityEventType.REMEDIATION_FAILED,
            execution.started_by,
            plan.device_id,
            f"Remediation execution failed for plan #{plan.id}: {failure_code}",
        )

    def scan_and_recover_stale_executions(self, timeout_minutes: int) -> int:
        """Crash recovery for stale RUNNING executions older than timeout_minutes."""
        now = self._now()
        from datetime import timedelta
        cutoff = now - timedelta(minutes=timeout_minutes)
        stale_execs = self._repo.get_stale_running_executions(cutoff)
        recovered_count = 0

        for exc in stale_execs:
            plan = self._repo.get_plan(exc.plan_id)
            if plan is None:
                continue

            if plan.status == PlanStatus.APPLYING:
                self._repo.update_status(
                    plan_id=plan.id,
                    expected_current_status=PlanStatus.APPLYING,
                    new_status=PlanStatus.FAILED,
                    updated_at=now,
                )
                failure_code = "INTERRUPTED"
            elif plan.status == PlanStatus.APPLIED:
                self._repo.update_status(
                    plan_id=plan.id,
                    expected_current_status=PlanStatus.APPLIED,
                    new_status=PlanStatus.FAILED,
                    updated_at=now,
                )
                failure_code = "INTERRUPTED_AFTER_WRITE"
            else:
                failure_code = "INTERRUPTED"

            upd_exec = replace(
                exc,
                finished_at=now,
                result=ExecutionResult.FAILED,
                failure_code=failure_code,
                needs_manual_attention=True,
            )
            self._repo.update_execution(upd_exec)
            self._repo.add_event(
                plan.id,
                now,
                "FAILED",
                exc.started_by,
                f"Execution timed out and was recovered as {failure_code}",
            )
            self._log_security_event(
                SecurityEventType.REMEDIATION_FAILED,
                exc.started_by,
                plan.device_id,
                f"Execution #{exc.id} recovered after crash/timeout ({failure_code})",
            )
            recovered_count += 1

        return recovered_count
