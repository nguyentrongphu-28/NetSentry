"""Unit tests for RemediationService (Spec 9.5, 9.6, 9.7)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.entities.remediation import PlanStatus, RemediationPlan, RiskLevel
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.domain.errors import (
    AccountLockedError,
    ActivePlanExistsError,
    FindingNotFailingError,
    ForbiddenError,
    InvalidTransitionError,
    NotEligibleError,
    PlanExpiredError,
    PlanNotFoundError,
    PlanStaleError,
    ReauthFailedError,
    RemediationDisabledError,
    SelfApprovalError,
    UserSessionRequiredError,
)
from app.repositories.audit_repository import SqliteAuditRepository
from app.repositories.database import connect, init_db
from app.repositories.device_repository import SqliteDeviceRepository
from app.repositories.sqlite_remediation_repository import SqliteRemediationRepository
from app.repositories.sqlite_security_event_repository import SQLiteSecurityEventRepository
from app.repositories.sqlite_session_repository import SQLiteSessionRepository
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher
from app.security.rate_limiter import InMemorySlidingWindowLimiter
from app.services.auth_service import AuthService
from app.services.remediation_service import RemediationService


class FakeClock:
    def __init__(self, start_time: datetime) -> None:
        self.current = start_time

    def __call__(self) -> datetime:
        return self.current

    def advance(self, minutes: float) -> None:
        self.current = self.current + timedelta(minutes=minutes)


@pytest.fixture
def service_env(tmp_path: Path):
    db_file = tmp_path / "test_remediation_service.db"
    init_db(db_file)
    conn = connect(db_file)

    clock = FakeClock(datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc))
    remediation_repo = SqliteRemediationRepository(conn)
    device_repo = SqliteDeviceRepository(db_file)
    audit_repo = SqliteAuditRepository(db_file)
    event_repo = SQLiteSecurityEventRepository(db_file)
    user_repo = SQLiteUserRepository(db_file)
    session_repo = SQLiteSessionRepository(db_file)

    hasher = Argon2PasswordHasher()
    limiter = InMemorySlidingWindowLimiter(max_requests=10, window_seconds=300)
    auth_service = AuthService(
        user_repo=user_repo,
        session_repo=session_repo,
        event_repo=event_repo,
        password_hasher=hasher,
        rate_limiter=limiter,
        max_failed_logins=3,
        lockout_minutes=15,
        session_ttl_minutes=480,
        clock=clock,
    )

    # Seed device
    now_iso = clock().isoformat()
    with conn:
        conn.execute(
            """
            INSERT INTO devices (device_id, name, host, port, platform, created_at, updated_at)
            VALUES ('Router-Core-01', 'Core Router', '192.168.1.1', 22, 'cisco_ios', ?, ?)
            """,
            (now_iso, now_iso),
        )

    # Seed users
    admin_hash = hasher.hash("AdminPass123!")
    admin2_hash = hasher.hash("Admin2Pass123!")
    op_hash = hasher.hash("OperatorPass123!")
    admin_u = user_repo.add("admin1", admin_hash, Role.ADMIN, must_change_password=False)
    admin2_u = user_repo.add("admin2", admin2_hash, Role.ADMIN, must_change_password=False)
    op_u = user_repo.add("operator1", op_hash, Role.OPERATOR, must_change_password=False)
    admin_id = admin_u.id
    admin2_id = admin2_u.id
    op_id = op_u.id

    # Seed initial completed audit run with failing NET-008 finding
    with conn:
        conn.execute(
            """
            INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at, pass_count, fail_count, unknown_count)
            VALUES (1, 'Router-Core-01', 'cisco_ios', 'COMPLETED', ?, ?, 0, 1, 0)
            """,
            (now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO findings (audit_run_id, rule_id, title, severity, status, evidence_json, rationale, remediation, verification, checked_at)
            VALUES (1, 'NET-008', 'HTTP Server Enabled', 'HIGH', 'FAIL', '["ip http server"]', 'Insecure', 'no ip http server', 'check', ?)
            """,
            (now_iso,),
        )

    service = RemediationService(
        remediation_repo=remediation_repo,
        device_repo=device_repo,
        audit_repo=audit_repo,
        auth_service=auth_service,
        security_event_repo=event_repo,
        enabled=True,
        proposal_ttl_minutes=120,
        approval_ttl_minutes=60,
        max_audit_age_minutes=60,
        require_distinct_approver=True,
        clock=clock,
    )

    return {
        "service": service,
        "clock": clock,
        "conn": conn,
        "admin_id": admin_id,
        "admin2_id": admin2_id,
        "op_id": op_id,
        "audit_repo": audit_repo,
        "event_repo": event_repo,
    }


class TestRemediationServicePropose:
    def test_propose_success(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
            persist_after_verify=False,
        )
        assert plan.id > 0
        assert plan.status == PlanStatus.PROPOSED
        assert plan.rule_id == "NET-008"
        assert plan.commands == ("no ip http server",)
        assert plan.persist_after_verify is False
        assert plan.proposed_by == "operator1"
        assert len(plan.plan_hash) == 64

    def test_propose_requires_user_session(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        with pytest.raises(UserSessionRequiredError):
            svc.propose(
                run_id=1,
                rule_id="NET-008",
                proposer_username="api-key",
                proposer_user_id=None,
            )

    def test_propose_disabled_raises(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        svc._enabled = False
        with pytest.raises(RemediationDisabledError):
            svc.propose(
                run_id=1,
                rule_id="NET-008",
                proposer_username="operator1",
                proposer_user_id=service_env["op_id"],
            )

    def test_propose_ineligible_rule(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        with pytest.raises(NotEligibleError):
            svc.propose(
                run_id=1,
                rule_id="NET-001",
                proposer_username="operator1",
                proposer_user_id=service_env["op_id"],
            )

    def test_propose_finding_not_failing(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        conn: sqlite3.Connection = service_env["conn"]
        # Update finding to PASS
        with conn:
            conn.execute("UPDATE findings SET status = 'PASS' WHERE rule_id = 'NET-008'")

        with pytest.raises(FindingNotFailingError):
            svc.propose(
                run_id=1,
                rule_id="NET-008",
                proposer_username="operator1",
                proposer_user_id=service_env["op_id"],
            )

    def test_propose_stale_when_audit_too_old(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        clock: FakeClock = service_env["clock"]
        # Advance clock by 61 minutes (exceeds max_audit_age_minutes=60)
        clock.advance(61)

        with pytest.raises(PlanStaleError, match="older than 60 minutes"):
            svc.propose(
                run_id=1,
                rule_id="NET-008",
                proposer_username="operator1",
                proposer_user_id=service_env["op_id"],
            )

    def test_propose_stale_when_newer_audit_exists(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        conn: sqlite3.Connection = service_env["conn"]
        clock: FakeClock = service_env["clock"]
        now_iso = clock().isoformat()

        # Insert newer audit run #2
        with conn:
            conn.execute(
                """
                INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at)
                VALUES (2, 'Router-Core-01', 'cisco_ios', 'COMPLETED', ?, ?)
                """,
                (now_iso, now_iso),
            )

        with pytest.raises(PlanStaleError, match="newer audit run exists"):
            svc.propose(
                run_id=1,  # run 1 is now not the latest
                rule_id="NET-008",
                proposer_username="operator1",
                proposer_user_id=service_env["op_id"],
            )

    def test_propose_duplicate_active_plan_raises(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
        )
        with pytest.raises(ActivePlanExistsError):
            svc.propose(
                run_id=1,
                rule_id="NET-008",
                proposer_username="operator1",
                proposer_user_id=service_env["op_id"],
            )


class TestRemediationServiceApprove:
    def test_approve_success(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
        )

        approved = svc.approve(
            plan_id=plan.id,
            approver_username="admin1",
            approver_user_id=service_env["admin_id"],
            approver_role=Role.ADMIN,
            password="AdminPass123!",
            client_ip="192.168.1.100",
        )
        assert approved.status == PlanStatus.APPROVED
        assert approved.decided_by == "admin1"
        assert approved.approved_plan_hash == plan.plan_hash

    def test_self_approval_blocked_when_required(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        event_repo = service_env["event_repo"]

        # Admin proposes
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="admin1",
            proposer_user_id=service_env["admin_id"],
        )

        # Same admin tries to approve
        with pytest.raises(SelfApprovalError):
            svc.approve(
                plan_id=plan.id,
                approver_username="admin1",
                approver_user_id=service_env["admin_id"],
                approver_role=Role.ADMIN,
                password="AdminPass123!",
            )

        # Check ACCESS_DENIED security event logged
        events = event_repo.list()
        assert any(e.event_type == SecurityEventType.ACCESS_DENIED for e in events)

        # Different admin CAN approve
        approved = svc.approve(
            plan_id=plan.id,
            approver_username="admin2",
            approver_user_id=service_env["admin2_id"],
            approver_role=Role.ADMIN,
            password="Admin2Pass123!",
        )
        assert approved.status == PlanStatus.APPROVED

    def test_self_approval_allowed_when_distinct_approver_disabled(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        svc._require_distinct_approver = False

        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="admin1",
            proposer_user_id=service_env["admin_id"],
        )

        approved = svc.approve(
            plan_id=plan.id,
            approver_username="admin1",
            approver_user_id=service_env["admin_id"],
            approver_role=Role.ADMIN,
            password="AdminPass123!",
        )
        assert approved.status == PlanStatus.APPROVED

    def test_approve_wrong_password_raises_reauth_failed(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
        )

        with pytest.raises(ReauthFailedError):
            svc.approve(
                plan_id=plan.id,
                approver_username="admin1",
                approver_user_id=service_env["admin_id"],
                approver_role=Role.ADMIN,
                password="WrongPassword!",
            )

    def test_approve_plan_expired_by_ttl(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        clock: FakeClock = service_env["clock"]
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
        )

        # Advance past proposal TTL (120 min)
        clock.advance(125)

        with pytest.raises(PlanExpiredError):
            svc.approve(
                plan_id=plan.id,
                approver_username="admin1",
                approver_user_id=service_env["admin_id"],
                approver_role=Role.ADMIN,
                password="AdminPass123!",
            )

        refreshed = svc.get_plan(plan.id)
        assert refreshed.status == PlanStatus.EXPIRED

    def test_approve_invalidated_when_newer_audit_exists(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        conn: sqlite3.Connection = service_env["conn"]
        clock: FakeClock = service_env["clock"]

        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
        )

        # Newer audit run arrives
        now_iso = clock().isoformat()
        with conn:
            conn.execute(
                """
                INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at)
                VALUES (2, 'Router-Core-01', 'cisco_ios', 'COMPLETED', ?, ?)
                """,
                (now_iso, now_iso),
            )

        with pytest.raises(PlanStaleError):
            svc.approve(
                plan_id=plan.id,
                approver_username="admin1",
                approver_user_id=service_env["admin_id"],
                approver_role=Role.ADMIN,
                password="AdminPass123!",
            )

        refreshed = svc.get_plan(plan.id)
        assert refreshed.status == PlanStatus.EXPIRED


class TestRemediationServiceRejectAndCancel:
    def test_reject_success(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
        )

        rejected = svc.reject(
            plan_id=plan.id,
            actor_username="admin1",
            actor_user_id=service_env["admin_id"],
            actor_role=Role.ADMIN,
            reason="Web GUI is required for maintenance window",
        )
        assert rejected.status == PlanStatus.REJECTED
        assert rejected.decided_by == "admin1"
        assert rejected.decision_reason == "Web GUI is required for maintenance window"

    def test_reject_requires_reason(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
        )

        with pytest.raises(ValueError, match="reason is required"):
            svc.reject(
                plan_id=plan.id,
                actor_username="admin1",
                actor_user_id=service_env["admin_id"],
                actor_role=Role.ADMIN,
                reason="   ",
            )

    def test_cancel_by_proposer_operator(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
        )

        cancelled = svc.cancel(
            plan_id=plan.id,
            actor_username="operator1",
            actor_user_id=service_env["op_id"],
            actor_role=Role.OPERATOR,
        )
        assert cancelled.status == PlanStatus.CANCELLED

    def test_cancel_other_proposer_plan_forbidden_for_operator(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="admin1",
            proposer_user_id=service_env["admin_id"],
        )

        with pytest.raises(ForbiddenError, match="Operators can only cancel plans they proposed"):
            svc.cancel(
                plan_id=plan.id,
                actor_username="operator1",
                actor_user_id=service_env["op_id"],
                actor_role=Role.OPERATOR,
            )

    def test_cancel_any_plan_allowed_for_admin(self, service_env) -> None:
        svc: RemediationService = service_env["service"]
        plan = svc.propose(
            run_id=1,
            rule_id="NET-008",
            proposer_username="operator1",
            proposer_user_id=service_env["op_id"],
        )

        cancelled = svc.cancel(
            plan_id=plan.id,
            actor_username="admin1",
            actor_user_id=service_env["admin_id"],
            actor_role=Role.ADMIN,
        )
        assert cancelled.status == PlanStatus.CANCELLED
