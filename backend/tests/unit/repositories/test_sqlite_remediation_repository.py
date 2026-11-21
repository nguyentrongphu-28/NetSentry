"""Unit tests for SqliteRemediationRepository (Spec 9.4)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.entities.remediation import (
    ExecutionMode,
    ExecutionResult,
    ExecutionStep,
    PlanStatus,
    RemediationExecution,
    RemediationPlan,
    RiskLevel,
)
from app.domain.errors import ActivePlanExistsError
from app.repositories.database import connect, init_db
from app.repositories.sqlite_remediation_repository import SqliteRemediationRepository


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    db_file = tmp_path / "test_remediation.db"
    init_db(db_file)
    conn = connect(db_file)

    # Seed dummy device and audit run
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            """
            INSERT INTO devices (device_id, name, host, port, platform, created_at, updated_at)
            VALUES ('Router-Core-01', 'Core Router', '192.168.1.1', 22, 'cisco_ios', ?, ?)
            """,
            (now, now),
        )
        conn.execute(
            """
            INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at)
            VALUES (101, 'Router-Core-01', 'cisco_ios', 'COMPLETED', ?, ?)
            """,
            (now, now),
        )
    return conn


def _make_plan(
    *,
    device_id: str = "Router-Core-01",
    rule_id: str = "NET-008",
    status: PlanStatus = PlanStatus.PROPOSED,
    expires_at: datetime | None = None,
) -> RemediationPlan:
    now = datetime.now(timezone.utc)
    exp = expires_at or now
    return RemediationPlan(
        id=0,
        device_id=device_id,
        run_id=101,
        rule_id=rule_id,
        template_id="NET-008-v1",
        template_version=1,
        risk_level=RiskLevel.LOW,
        commands=("no ip http server",),
        persist_after_verify=False,
        plan_hash="fakehash123",
        status=status,
        proposed_by="operator1",
        proposed_at=now,
        decided_by=None,
        decided_at=None,
        decision_reason=None,
        approved_plan_hash=None,
        expires_at=exp,
        updated_at=now,
    )


class TestSqliteRemediationRepository:
    def test_create_and_get_plan(self, db_conn: sqlite3.Connection) -> None:
        repo = SqliteRemediationRepository(db_conn)
        plan = _make_plan()
        plan_id = repo.create_plan(plan)
        assert plan_id > 0

        fetched = repo.get_plan(plan_id)
        assert fetched is not None
        assert fetched.id == plan_id
        assert fetched.device_id == "Router-Core-01"
        assert fetched.rule_id == "NET-008"
        assert fetched.commands == ("no ip http server",)
        assert fetched.status == PlanStatus.PROPOSED

    def test_partial_unique_index_blocks_duplicate_active_plan(
        self, db_conn: sqlite3.Connection
    ) -> None:
        repo = SqliteRemediationRepository(db_conn)
        plan1 = _make_plan()
        repo.create_plan(plan1)

        # Attempting to create second active plan for same device and rule must raise ActivePlanExistsError
        plan2 = _make_plan()
        with pytest.raises(ActivePlanExistsError):
            repo.create_plan(plan2)

    def test_partial_unique_index_allows_new_plan_after_final_state(
        self, db_conn: sqlite3.Connection
    ) -> None:
        repo = SqliteRemediationRepository(db_conn)
        plan1 = _make_plan()
        plan_id1 = repo.create_plan(plan1)

        # Reject plan1
        now = datetime.now(timezone.utc)
        success = repo.update_status(
            plan_id=plan_id1,
            expected_current_status=PlanStatus.PROPOSED,
            new_status=PlanStatus.REJECTED,
            decided_by="admin",
            decided_at=now,
            decision_reason="Not needed right now",
            updated_at=now,
        )
        assert success is True

        # Now creating a new plan for the same device and rule should succeed!
        plan2 = _make_plan()
        plan_id2 = repo.create_plan(plan2)
        assert plan_id2 > plan_id1

    def test_atomic_status_update(self, db_conn: sqlite3.Connection) -> None:
        repo = SqliteRemediationRepository(db_conn)
        plan_id = repo.create_plan(_make_plan())

        now = datetime.now(timezone.utc)
        # Transition from PROPOSED to APPROVED
        ok = repo.update_status(
            plan_id=plan_id,
            expected_current_status=PlanStatus.PROPOSED,
            new_status=PlanStatus.APPROVED,
            decided_by="admin",
            decided_at=now,
            approved_plan_hash="fakehash123",
            updated_at=now,
        )
        assert ok is True

        # Repeating the same transition must fail because status is now APPROVED, not PROPOSED
        ok_second = repo.update_status(
            plan_id=plan_id,
            expected_current_status=PlanStatus.PROPOSED,
            new_status=PlanStatus.APPROVED,
            decided_by="admin2",
            decided_at=now,
            updated_at=now,
        )
        assert ok_second is False

    def test_cascade_delete_on_device_deletion(self, db_conn: sqlite3.Connection) -> None:
        repo = SqliteRemediationRepository(db_conn)
        plan_id = repo.create_plan(_make_plan())
        repo.add_event(plan_id, datetime.now(timezone.utc), "PROPOSED", "operator1", "Plan proposed")

        # Delete device
        with db_conn:
            db_conn.execute("DELETE FROM devices WHERE device_id = 'Router-Core-01'")

        # Plan and events should be cascade deleted
        assert repo.get_plan(plan_id) is None
        assert repo.list_events(plan_id) == []

    def test_events_append_and_list(self, db_conn: sqlite3.Connection) -> None:
        repo = SqliteRemediationRepository(db_conn)
        plan_id = repo.create_plan(_make_plan())

        now1 = datetime.now(timezone.utc)
        repo.add_event(plan_id, now1, "PROPOSED", "operator1", "Proposed by operator1")
        now2 = datetime.now(timezone.utc)
        repo.add_event(plan_id, now2, "APPROVED", "admin", "Approved with step-up auth")

        events = repo.list_events(plan_id)
        assert len(events) == 2
        assert events[0].event_type == "PROPOSED"
        assert events[1].event_type == "APPROVED"
        assert events[0].actor == "operator1"
        assert events[1].actor == "admin"

    def test_acquire_device_for_applying_and_device_busy(self, db_conn: sqlite3.Connection) -> None:
        repo = SqliteRemediationRepository(db_conn)
        now = datetime.now(timezone.utc)

        # Plan 1 for Router-Core-01
        plan1_id = repo.create_plan(_make_plan(rule_id="NET-008", status=PlanStatus.APPROVED))
        # Plan 2 for Router-Core-01 (different rule)
        plan2_id = repo.create_plan(_make_plan(rule_id="NET-004", status=PlanStatus.APPROVED))

        # Initially device is not busy
        assert not repo.is_device_busy("Router-Core-01")

        # Acquire device for plan 1 -> succeeds
        acquired = repo.acquire_device_for_applying(plan1_id, "Router-Core-01", now)
        assert acquired is True
        assert repo.is_device_busy("Router-Core-01")
        assert repo.get_plan(plan1_id).status == PlanStatus.APPLYING

        # Acquire device for plan 2 on same device -> fails because device is busy
        acquired_second = repo.acquire_device_for_applying(plan2_id, "Router-Core-01", now)
        assert acquired_second is False
        assert repo.get_plan(plan2_id).status == PlanStatus.APPROVED

    def test_execution_crud_and_attention_flow(self, db_conn: sqlite3.Connection) -> None:
        repo = SqliteRemediationRepository(db_conn)
        now = datetime.now(timezone.utc)
        plan_id = repo.create_plan(_make_plan(status=PlanStatus.APPLYING))

        step1 = ExecutionStep(step="PRECHECK_AUDIT", status="OK", at=now, detail="Precheck passed")
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
            pre_run_id=101,
            post_run_id=None,
            rollback_run_id=None,
            persist_status="NOT_REQUESTED",
            needs_manual_attention=False,
            steps=(step1,),
        )
        exec_id = repo.create_execution(execution)
        assert exec_id > 0

        # Fetch execution
        fetched = repo.get_execution(exec_id)
        assert fetched is not None
        assert fetched.id == exec_id
        assert fetched.plan_id == plan_id
        assert fetched.result == ExecutionResult.RUNNING
        assert len(fetched.steps) == 1
        assert fetched.steps[0].step == "PRECHECK_AUDIT"

        # Update execution to FAILED + needs_manual_attention
        step2 = ExecutionStep(step="WRITE", status="FAILED", at=now, detail="Device rejected command")
        updated_exec = RemediationExecution(
            id=exec_id,
            plan_id=plan_id,
            mode=ExecutionMode.LIVE,
            started_at=now,
            finished_at=now,
            started_by="admin1",
            result=ExecutionResult.FAILED,
            failure_code="WRITE_REJECTED",
            changes_sent=True,
            pre_run_id=101,
            post_run_id=None,
            rollback_run_id=None,
            persist_status="NOT_REQUESTED",
            needs_manual_attention=True,
            steps=(step1, step2),
        )
        repo.update_execution(updated_exec)

        # Check attention list
        attention_list = repo.list_attention_executions()
        assert len(attention_list) == 1
        p, e = attention_list[0]
        assert p.id == plan_id
        assert e.id == exec_id
        assert e.needs_manual_attention is True
        assert e.acknowledged_at is None

        # Acknowledge attention
        ack_ok = repo.acknowledge_attention(plan_id, "admin2", "Checked router console manually", now)
        assert ack_ok is True

        # Attention list should now be empty
        assert len(repo.list_attention_executions()) == 0
        refetched = repo.get_execution(exec_id)
        assert refetched.acknowledged_by == "admin2"
        assert refetched.acknowledgement_note == "Checked router console manually"

