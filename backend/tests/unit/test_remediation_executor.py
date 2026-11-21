"""Unit tests for RemediationExecutor: live execution, verification, rollback, dry-run, and crash recovery (Spec 10.4-10.8, 10.10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from app.connectors.fake_config_writer import FakeConfigWriter, FakeConfigWriterFactory
from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.audit_run import AuditRunDetail, AuditRunSummary
from app.domain.entities.device import Device
from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.entities.remediation import (
    ExecutionMode,
    ExecutionResult,
    PlanStatus,
    RemediationExecution,
    RemediationPlan,
    RiskLevel,
)
from app.domain.entities.security_event import SecurityEventType
from app.domain.errors import (
    WriteAuthFailedError,
    WriteConnectionError,
    WriteRejectedError,
)
from app.repositories.database import init_db
from app.repositories.device_repository import SqliteDeviceRepository
from app.repositories.sqlite_remediation_repository import SqliteRemediationRepository
from app.repositories.sqlite_security_event_repository import SQLiteSecurityEventRepository
from app.services.diff_service import DiffService
from app.services.remediation_executor import ExecutionRunner, RemediationExecutor


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, minutes: float) -> None:
        self.current += timedelta(minutes=minutes)


def _make_finding(
    rule_id: str,
    status: FindingStatus,
    title: str = "Test Finding",
    severity: Severity = Severity.MEDIUM,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        title=title,
        severity=severity,
        status=status,
        evidence=("evidence line",),
        rationale="rationale",
        remediation="remediation",
        verification="verification",
    )


def _make_audit_run(
    run_id: int,
    device_id: str,
    status: AuditStatus = AuditStatus.COMPLETED,
    findings: tuple[Finding, ...] = (),
) -> AuditRunDetail:
    now = datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc)
    summary = AuditRunSummary(
        id=run_id,
        device_id=device_id,
        platform="cisco_ios",
        status=status,
        started_at=now,
        finished_at=now,
        hostname="R1",
        error_code=None,
        error_message=None,
        pass_count=sum(1 for f in findings if f.status == FindingStatus.PASS),
        fail_count=sum(1 for f in findings if f.status == FindingStatus.FAIL),
        unknown_count=sum(1 for f in findings if f.status == FindingStatus.UNKNOWN),
    )
    return AuditRunDetail(summary=summary, findings=list(findings))


@pytest.fixture
def executor_env(tmp_path: Path):
    db_file = tmp_path / "test_executor.db"
    init_db(db_file)

    clock = FakeClock(datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc))
    device_repo = SqliteDeviceRepository(db_file)
    remediation_repo = SqliteRemediationRepository(db_file)
    security_event_repo = SQLiteSecurityEventRepository(db_file)

    # Add test device
    now = clock()
    dev = Device(
        device_id="Router-01",
        name="Core Router",
        host="192.168.1.1",
        port=22,
        platform="cisco_ios",
        created_at=now,
        updated_at=now,
    )
    device_repo.add(dev)

    diff_service = DiffService()
    mock_audit_service = MagicMock()
    fake_writer = FakeConfigWriter()
    writer_factory = FakeConfigWriterFactory(fake_writer)

    # Use synchronous runner for tests
    class SyncExecutionRunner(ExecutionRunner):
        def submit(self, fn, *args, **kwargs):
            fn(*args, **kwargs)

    sync_runner = SyncExecutionRunner()

    executor = RemediationExecutor(
        remediation_repo=remediation_repo,
        writer_factory=writer_factory,
        audit_run_service=mock_audit_service,
        diff_service=diff_service,
        device_repo=device_repo,
        security_event_repo=security_event_repo,
        clock=clock,
        runner=sync_runner,
    )

    return {
        "executor": executor,
        "repo": remediation_repo,
        "device_repo": device_repo,
        "sec_repo": security_event_repo,
        "audit_service": mock_audit_service,
        "writer": fake_writer,
        "clock": clock,
    }


def _create_approved_plan(
    repo: SqliteRemediationRepository,
    *,
    rule_id: str = "NET-008",
    persist_after_verify: bool = False,
    status: PlanStatus = PlanStatus.APPROVED,
) -> int:
    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    plan = RemediationPlan(
        id=0,
        device_id="Router-01",
        run_id=101,
        rule_id=rule_id,
        template_id=f"{rule_id}-v2",
        template_version=2,
        risk_level=RiskLevel.LOW,
        commands=("no ip http server",) if rule_id == "NET-008" else ("service password-encryption",),
        persist_after_verify=persist_after_verify,
        plan_hash="fakehash",
        status=status,
        proposed_by="operator1",
        proposed_at=now,
        decided_by="admin1",
        decided_at=now,
        decision_reason="Approved",
        approved_plan_hash="fakehash",
        expires_at=now + timedelta(hours=1),
        updated_at=now,
    )
    return repo.create_plan(plan)


class TestRemediationExecutorLive:
    def test_live_execution_success(self, executor_env) -> None:
        """Spec 10.4: Pre FAIL -> write -> post PASS, no regression -> VERIFIED."""
        env = executor_env
        repo: SqliteRemediationRepository = env["repo"]
        executor: RemediationExecutor = env["executor"]
        writer: FakeConfigWriter = env["writer"]
        audit_service = env["audit_service"]

        plan_id = _create_approved_plan(repo, rule_id="NET-008", persist_after_verify=True)
        # Transition to APPLYING as apply() does
        repo.update_status(plan_id, PlanStatus.APPROVED, PlanStatus.APPLYING, updated_at=env["clock"]())

        # Precheck audit has NET-008 FAIL
        pre_run = _make_audit_run(201, "Router-01", findings=(_make_finding("NET-008", FindingStatus.FAIL),))
        # Post audit has NET-008 PASS
        post_run = _make_audit_run(202, "Router-01", findings=(_make_finding("NET-008", FindingStatus.PASS),))
        audit_service.run_audit.side_effect = [pre_run, post_run]

        # Create execution record
        now = env["clock"]()
        execution = RemediationExecution(
            id=0,
            plan_id=plan_id,
            mode=ExecutionMode.LIVE,
            started_at=now,
            finished_at=None,
            started_by="admin1",
            result=ExecutionResult.RUNNING,
            failure_code=None,
            changes_sent=False,
            pre_run_id=None,
            post_run_id=None,
            rollback_run_id=None,
            persist_status="NOT_REQUESTED",
            needs_manual_attention=False,
            steps=(),
        )
        exec_id = repo.create_execution(execution)

        executor.execute_async(plan_id, exec_id)

        # Assertions
        updated_plan = repo.get_plan(plan_id)
        assert updated_plan.status == PlanStatus.VERIFIED

        updated_exec = repo.get_execution(exec_id)
        assert updated_exec.result == ExecutionResult.VERIFIED
        assert updated_exec.changes_sent is True
        assert updated_exec.pre_run_id == 201
        assert updated_exec.post_run_id == 202
        assert updated_exec.persist_status == "SAVED"
        assert updated_exec.needs_manual_attention is False

        # Writer received exact commands and save_config was called
        assert writer.applied_commands == ["no ip http server"]
        assert writer.save_config_called is True

    def test_precheck_audit_not_failing_aborts_without_writer(self, executor_env) -> None:
        """Spec 10.5: Rule already PASS in precheck -> FAILED, writer NEVER called."""
        env = executor_env
        repo: SqliteRemediationRepository = env["repo"]
        executor: RemediationExecutor = env["executor"]
        writer: FakeConfigWriter = env["writer"]
        writer.raise_if_called = True  # proves writer is never called

        plan_id = _create_approved_plan(repo, rule_id="NET-008")
        repo.update_status(plan_id, PlanStatus.APPROVED, PlanStatus.APPLYING, updated_at=env["clock"]())

        # Precheck audit already has NET-008 PASS!
        pre_run = _make_audit_run(201, "Router-01", findings=(_make_finding("NET-008", FindingStatus.PASS),))
        env["audit_service"].run_audit.return_value = pre_run

        now = env["clock"]()
        execution = RemediationExecution(
            id=0,
            plan_id=plan_id,
            mode=ExecutionMode.LIVE,
            started_at=now,
            finished_at=None,
            started_by="admin1",
            result=ExecutionResult.RUNNING,
            failure_code=None,
            changes_sent=False,
            pre_run_id=None,
            post_run_id=None,
            rollback_run_id=None,
            persist_status="NOT_REQUESTED",
            needs_manual_attention=False,
            steps=(),
        )
        exec_id = repo.create_execution(execution)

        executor.execute_async(plan_id, exec_id)

        updated_plan = repo.get_plan(plan_id)
        assert updated_plan.status == PlanStatus.FAILED

        updated_exec = repo.get_execution(exec_id)
        assert updated_exec.result == ExecutionResult.FAILED
        assert updated_exec.failure_code == "PRECHECK_NOT_FAILING"
        assert updated_exec.changes_sent is False
        assert updated_exec.needs_manual_attention is False
        assert len(writer.applied_commands) == 0

    def test_write_rejected_error_handling(self, executor_env) -> None:
        """Spec 10.6: Device rejects command -> FAILED, changes_sent=False, no rollback."""
        env = executor_env
        repo: SqliteRemediationRepository = env["repo"]
        executor: RemediationExecutor = env["executor"]
        writer: FakeConfigWriter = env["writer"]
        writer.fail_at_command_index = 0
        writer.fail_exception = WriteRejectedError("Device rejected command")

        plan_id = _create_approved_plan(repo, rule_id="NET-008")
        repo.update_status(plan_id, PlanStatus.APPROVED, PlanStatus.APPLYING, updated_at=env["clock"]())

        pre_run = _make_audit_run(201, "Router-01", findings=(_make_finding("NET-008", FindingStatus.FAIL),))
        env["audit_service"].run_audit.return_value = pre_run

        now = env["clock"]()
        execution = RemediationExecution(
            id=0,
            plan_id=plan_id,
            mode=ExecutionMode.LIVE,
            started_at=now,
            finished_at=None,
            started_by="admin1",
            result=ExecutionResult.RUNNING,
            failure_code=None,
            changes_sent=False,
            pre_run_id=None,
            post_run_id=None,
            rollback_run_id=None,
            persist_status="NOT_REQUESTED",
            needs_manual_attention=False,
            steps=(),
        )
        exec_id = repo.create_execution(execution)

        executor.execute_async(plan_id, exec_id)

        assert repo.get_plan(plan_id).status == PlanStatus.FAILED
        updated_exec = repo.get_execution(exec_id)
        assert updated_exec.result == ExecutionResult.FAILED
        assert updated_exec.failure_code == "WRITE_REJECTED"
        assert updated_exec.changes_sent is False
        assert updated_exec.needs_manual_attention is False

    def test_verification_failure_triggers_rollback_on_reversible_template(self, executor_env) -> None:
        """Spec 10.7: Verification fails -> rollback with 'ip http server' -> ROLLED_BACK."""
        env = executor_env
        repo: SqliteRemediationRepository = env["repo"]
        executor: RemediationExecutor = env["executor"]
        writer: FakeConfigWriter = env["writer"]
        audit_service = env["audit_service"]

        plan_id = _create_approved_plan(repo, rule_id="NET-008")
        repo.update_status(plan_id, PlanStatus.APPROVED, PlanStatus.APPLYING, updated_at=env["clock"]())

        pre_run = _make_audit_run(201, "Router-01", findings=(_make_finding("NET-008", FindingStatus.FAIL),))
        # Post audit still has NET-008 FAIL!
        post_run = _make_audit_run(202, "Router-01", findings=(_make_finding("NET-008", FindingStatus.FAIL),))
        # Post rollback audit confirms back to pre-audit baseline
        rollback_run = _make_audit_run(203, "Router-01", findings=(_make_finding("NET-008", FindingStatus.FAIL),))
        audit_service.run_audit.side_effect = [pre_run, post_run, rollback_run]

        now = env["clock"]()
        execution = RemediationExecution(
            id=0,
            plan_id=plan_id,
            mode=ExecutionMode.LIVE,
            started_at=now,
            finished_at=None,
            started_by="admin1",
            result=ExecutionResult.RUNNING,
            failure_code=None,
            changes_sent=False,
            pre_run_id=None,
            post_run_id=None,
            rollback_run_id=None,
            persist_status="NOT_REQUESTED",
            needs_manual_attention=False,
            steps=(),
        )
        exec_id = repo.create_execution(execution)

        executor.execute_async(plan_id, exec_id)

        assert repo.get_plan(plan_id).status == PlanStatus.ROLLED_BACK
        updated_exec = repo.get_execution(exec_id)
        assert updated_exec.result == ExecutionResult.ROLLED_BACK
        assert updated_exec.rollback_run_id == 203
        assert updated_exec.needs_manual_attention is False
        assert writer.rollback_commands == ["ip http server"]

    def test_irreversible_template_verification_failure_marks_verify_failed(self, executor_env) -> None:
        """Spec 10.7: NET-004 verification failure -> VERIFY_FAILED + needs_manual_attention."""
        env = executor_env
        repo: SqliteRemediationRepository = env["repo"]
        executor: RemediationExecutor = env["executor"]
        writer: FakeConfigWriter = env["writer"]
        audit_service = env["audit_service"]

        plan_id = _create_approved_plan(repo, rule_id="NET-004")
        repo.update_status(plan_id, PlanStatus.APPROVED, PlanStatus.APPLYING, updated_at=env["clock"]())

        pre_run = _make_audit_run(201, "Router-01", findings=(_make_finding("NET-004", FindingStatus.FAIL),))
        # Post audit still has NET-004 FAIL
        post_run = _make_audit_run(202, "Router-01", findings=(_make_finding("NET-004", FindingStatus.FAIL),))
        audit_service.run_audit.side_effect = [pre_run, post_run]

        now = env["clock"]()
        execution = RemediationExecution(
            id=0,
            plan_id=plan_id,
            mode=ExecutionMode.LIVE,
            started_at=now,
            finished_at=None,
            started_by="admin1",
            result=ExecutionResult.RUNNING,
            failure_code=None,
            changes_sent=False,
            pre_run_id=None,
            post_run_id=None,
            rollback_run_id=None,
            persist_status="NOT_REQUESTED",
            needs_manual_attention=False,
            steps=(),
        )
        exec_id = repo.create_execution(execution)

        executor.execute_async(plan_id, exec_id)

        assert repo.get_plan(plan_id).status == PlanStatus.VERIFY_FAILED
        updated_exec = repo.get_execution(exec_id)
        assert updated_exec.result == ExecutionResult.VERIFY_FAILED
        assert updated_exec.needs_manual_attention is True
        # Rollback commands should not have been called because NET-004 is irreversible
        assert len(writer.rollback_commands) == 0


class TestRemediationExecutorDryRunAndRecovery:
    def test_dry_run_never_touches_writer_and_keeps_approved_status(self, executor_env) -> None:
        """Spec 10.8: Dry run runs real precheck, previews commands, does not touch writer."""
        env = executor_env
        repo: SqliteRemediationRepository = env["repo"]
        executor: RemediationExecutor = env["executor"]
        writer: FakeConfigWriter = env["writer"]
        writer.raise_if_called = True  # proves writer is never opened

        plan_id = _create_approved_plan(repo, rule_id="NET-008")
        # Plan stays in APPROVED

        pre_run = _make_audit_run(201, "Router-01", findings=(_make_finding("NET-008", FindingStatus.FAIL),))
        env["audit_service"].run_audit.return_value = pre_run

        now = env["clock"]()
        execution = RemediationExecution(
            id=0,
            plan_id=plan_id,
            mode=ExecutionMode.DRY_RUN,
            started_at=now,
            finished_at=None,
            started_by="admin1",
            result=ExecutionResult.RUNNING,
            failure_code=None,
            changes_sent=False,
            pre_run_id=None,
            post_run_id=None,
            rollback_run_id=None,
            persist_status="NOT_REQUESTED",
            needs_manual_attention=False,
            steps=(),
        )
        exec_id = repo.create_execution(execution)

        executor.execute_async(plan_id, exec_id)

        # Plan status MUST STILL BE APPROVED
        assert repo.get_plan(plan_id).status == PlanStatus.APPROVED
        updated_exec = repo.get_execution(exec_id)
        assert updated_exec.result == ExecutionResult.DRY_RUN_OK
        assert updated_exec.pre_run_id == 201
        assert any(s.step == "DRY_RUN_PREVIEW" for s in updated_exec.steps)

    def test_crash_recovery_recovers_stale_running_executions(self, executor_env) -> None:
        """Spec 10.10: Stale RUNNING executions transitioned to FAILED + needs_manual_attention."""
        env = executor_env
        repo: SqliteRemediationRepository = env["repo"]
        executor: RemediationExecutor = env["executor"]
        clock: FakeClock = env["clock"]

        # Create 2 plans and stale executions
        plan1_id = _create_approved_plan(repo, rule_id="NET-008")
        repo.update_status(plan1_id, PlanStatus.APPROVED, PlanStatus.APPLYING, updated_at=clock())

        start_time = clock()
        exec1 = RemediationExecution(
            id=0,
            plan_id=plan1_id,
            mode=ExecutionMode.LIVE,
            started_at=start_time,
            finished_at=None,
            started_by="admin1",
            result=ExecutionResult.RUNNING,
            failure_code=None,
            changes_sent=False,
            pre_run_id=None,
            post_run_id=None,
            rollback_run_id=None,
            persist_status="NOT_REQUESTED",
            needs_manual_attention=False,
            steps=(),
        )
        exec1_id = repo.create_execution(exec1)

        # Advance clock by 30 minutes (exceeds 15 minute timeout)
        clock.advance(30)

        recovered = executor.scan_and_recover_stale_executions(timeout_minutes=15)
        assert recovered == 1

        assert repo.get_plan(plan1_id).status == PlanStatus.FAILED
        recovered_exec = repo.get_execution(exec1_id)
        assert recovered_exec.result == ExecutionResult.FAILED
        assert recovered_exec.failure_code == "INTERRUPTED"
        assert recovered_exec.needs_manual_attention is True
