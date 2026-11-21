"""SQLite implementation of RemediationRepository."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from datetime import datetime
from typing import Any, Generator

from app.domain.entities.remediation import (
    ExecutionMode,
    ExecutionResult,
    ExecutionStep,
    PlanEvent,
    PlanStatus,
    RemediationExecution,
    RemediationPlan,
    RiskLevel,
)
from app.domain.errors import ActivePlanExistsError
from app.domain.interfaces.remediation_repository import RemediationRepository


def _parse_iso(val: str | None) -> datetime | None:
    if not val:
        return None
    return datetime.fromisoformat(val)


def _row_to_plan(row: sqlite3.Row) -> RemediationPlan:
    commands_raw = json.loads(row["commands_json"])
    return RemediationPlan(
        id=row["id"],
        device_id=row["device_id"],
        run_id=row["run_id"],
        rule_id=row["rule_id"],
        template_id=row["template_id"],
        template_version=row["template_version"],
        risk_level=RiskLevel(row["risk_level"]),
        commands=tuple(commands_raw),
        persist_after_verify=bool(row["persist_after_verify"]),
        plan_hash=row["plan_hash"],
        status=PlanStatus(row["status"]),
        proposed_by=row["proposed_by"],
        proposed_at=datetime.fromisoformat(row["proposed_at"]),
        decided_by=row["decided_by"],
        decided_at=_parse_iso(row["decided_at"]),
        decision_reason=row["decision_reason"],
        approved_plan_hash=row["approved_plan_hash"],
        expires_at=datetime.fromisoformat(row["expires_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_event(row: sqlite3.Row) -> PlanEvent:
    return PlanEvent(
        id=row["id"],
        plan_id=row["plan_id"],
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
        actor=row["actor"],
        event_type=row["event_type"],
        detail=row["detail"],
    )


def _row_to_execution(row: sqlite3.Row) -> RemediationExecution:
    steps_raw = json.loads(row["steps_json"])
    steps = tuple(
        ExecutionStep(
            step=s["step"],
            status=s["status"],
            at=datetime.fromisoformat(s["at"]),
            detail=s.get("detail"),
        )
        for s in steps_raw
    )
    return RemediationExecution(
        id=row["id"],
        plan_id=row["plan_id"],
        mode=ExecutionMode(row["mode"]),
        started_at=datetime.fromisoformat(row["started_at"]),
        finished_at=_parse_iso(row["finished_at"]),
        started_by=row["started_by"],
        result=ExecutionResult(row["result"]),
        failure_code=row["failure_code"],
        changes_sent=bool(row["changes_sent"]),
        pre_run_id=row["pre_run_id"],
        post_run_id=row["post_run_id"],
        rollback_run_id=row["rollback_run_id"],
        persist_status=row["persist_status"],
        needs_manual_attention=bool(row["needs_manual_attention"]),
        steps=steps,
        acknowledged_at=_parse_iso(row["acknowledged_at"]),
        acknowledged_by=row["acknowledged_by"],
        acknowledgement_note=row["acknowledgement_note"],
    )



class SqliteRemediationRepository(RemediationRepository):
    """SQLite implementation of the remediation repository."""

    def __init__(self, conn: sqlite3.Connection | Path | str | Any) -> None:
        if isinstance(conn, sqlite3.Connection):
            self._conn: sqlite3.Connection | None = conn
            self._db_path: Path | None = None
        else:
            self._conn = None
            self._db_path = Path(conn)

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        if self._conn is not None:
            yield self._conn
        else:
            from app.repositories.database import connect
            assert self._db_path is not None
            c = connect(self._db_path)
            try:
                yield c
            finally:
                c.close()

    def create_plan(self, plan: RemediationPlan) -> int:
        query = """
            INSERT INTO remediation_plans (
                device_id, run_id, rule_id, template_id, template_version,
                risk_level, commands_json, persist_after_verify, plan_hash,
                status, proposed_by, proposed_at, decided_by, decided_at,
                decision_reason, approved_plan_hash, expires_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            plan.device_id,
            plan.run_id,
            plan.rule_id,
            plan.template_id,
            plan.template_version,
            plan.risk_level.value,
            json.dumps(list(plan.commands)),
            1 if plan.persist_after_verify else 0,
            plan.plan_hash,
            plan.status.value,
            plan.proposed_by,
            plan.proposed_at.isoformat(),
            plan.decided_by,
            plan.decided_at.isoformat() if plan.decided_at else None,
            plan.decision_reason,
            plan.approved_plan_hash,
            plan.expires_at.isoformat(),
            plan.updated_at.isoformat(),
        )
        try:
            with self._get_conn() as conn:
                with conn:
                    cursor = conn.execute(query, params)
                    return cursor.lastrowid  # type: ignore[return-value]
        except sqlite3.IntegrityError as err:
            if "idx_plan_active" in str(err) or "UNIQUE" in str(err).upper():
                raise ActivePlanExistsError(
                    f"An active remediation plan already exists for device {plan.device_id!r} and rule {plan.rule_id!r}."
                ) from err
            raise

    def get_plan(self, plan_id: int) -> RemediationPlan | None:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM remediation_plans WHERE id = ?",
                (plan_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_plan(row)

    def list_plans_for_device(
        self, device_id: str, status: PlanStatus | None = None, limit: int = 30
    ) -> list[RemediationPlan]:
        clamped_limit = max(1, min(limit, 200))
        with self._get_conn() as conn:
            if status is not None:
                cursor = conn.execute(
                    """
                    SELECT * FROM remediation_plans
                    WHERE device_id = ? AND status = ?
                    ORDER BY proposed_at DESC, id DESC
                    LIMIT ?
                    """,
                    (device_id, status.value, clamped_limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM remediation_plans
                    WHERE device_id = ?
                    ORDER BY proposed_at DESC, id DESC
                    LIMIT ?
                    """,
                    (device_id, clamped_limit),
                )
            return [_row_to_plan(r) for r in cursor.fetchall()]

    def get_active_plan(self, device_id: str, rule_id: str) -> RemediationPlan | None:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM remediation_plans
                WHERE device_id = ? AND rule_id = ?
                  AND status IN ('PROPOSED', 'APPROVED', 'APPLYING')
                LIMIT 1
                """,
                (device_id, rule_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_plan(row)

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
        query = """
            UPDATE remediation_plans
            SET status = ?,
                decided_by = coalesce(?, decided_by),
                decided_at = coalesce(?, decided_at),
                decision_reason = coalesce(?, decision_reason),
                approved_plan_hash = coalesce(?, approved_plan_hash),
                expires_at = coalesce(?, expires_at),
                updated_at = ?
            WHERE id = ? AND status = ?
        """
        params = (
            new_status.value,
            decided_by,
            decided_at.isoformat() if decided_at else None,
            decision_reason,
            approved_plan_hash,
            expires_at.isoformat() if expires_at else None,
            updated_at.isoformat(),
            plan_id,
            expected_current_status.value,
        )
        with self._get_conn() as conn:
            with conn:
                cursor = conn.execute(query, params)
                return cursor.rowcount == 1

    def expire_stale_plans(self, now: datetime) -> list[RemediationPlan]:
        now_iso = now.isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM remediation_plans
                WHERE status IN ('PROPOSED', 'APPROVED')
                  AND expires_at <= ?
                """,
                (now_iso,),
            )
            stale_rows = cursor.fetchall()
        expired_plans: list[RemediationPlan] = []

        for row in stale_rows:
            plan_id = row["id"]
            current_status = PlanStatus(row["status"])
            updated = self.update_status(
                plan_id=plan_id,
                expected_current_status=current_status,
                new_status=PlanStatus.EXPIRED,
                updated_at=now,
            )
            if updated:
                self.add_event(
                    plan_id=plan_id,
                    occurred_at=now,
                    event_type="EXPIRED",
                    actor=None,
                    detail="Plan expired due to TTL timeout",
                )
                refreshed = self.get_plan(plan_id)
                if refreshed:
                    expired_plans.append(refreshed)

        return expired_plans

    def add_event(
        self,
        plan_id: int,
        occurred_at: datetime,
        event_type: str,
        actor: str | None = None,
        detail: str | None = None,
    ) -> int:
        clean_detail = detail[:200] if detail else None
        query = """
            INSERT INTO remediation_events (plan_id, occurred_at, actor, event_type, detail)
            VALUES (?, ?, ?, ?, ?)
        """
        with self._get_conn() as conn:
            with conn:
                cursor = conn.execute(
                    query,
                    (plan_id, occurred_at.isoformat(), actor, event_type, clean_detail),
                )
                return cursor.lastrowid  # type: ignore[return-value]

    def list_events(self, plan_id: int) -> list[PlanEvent]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT id, plan_id, occurred_at, actor, event_type, detail FROM remediation_events WHERE plan_id = ? ORDER BY id ASC",
                (plan_id,),
            )
            return [_row_to_event(r) for r in cursor.fetchall()]

    def acquire_device_for_applying(
        self,
        plan_id: int,
        device_id: str,
        updated_at: datetime,
    ) -> bool:
        """Atomically transition plan from APPROVED to APPLYING with device lock."""
        query = """
            UPDATE remediation_plans
            SET status = 'APPLYING', updated_at = ?
            WHERE id = ? AND status = 'APPROVED'
              AND NOT EXISTS (
                  SELECT 1 FROM remediation_plans
                  WHERE device_id = ? AND status IN ('APPLYING', 'APPLIED')
              )
        """
        with self._get_conn() as conn:
            with conn:
                cursor = conn.execute(query, (updated_at.isoformat(), plan_id, device_id))
                return cursor.rowcount == 1

    def is_device_busy(self, device_id: str) -> bool:
        """Return True if any plan for device_id is in APPLYING or APPLIED."""
        query = """
            SELECT 1 FROM remediation_plans
            WHERE device_id = ? AND status IN ('APPLYING', 'APPLIED')
            LIMIT 1
        """
        with self._get_conn() as conn:
            cursor = conn.execute(query, (device_id,))
            return cursor.fetchone() is not None

    def create_execution(self, execution: RemediationExecution) -> int:
        steps_json = json.dumps([
            {
                "step": s.step,
                "status": s.status,
                "at": s.at.isoformat(),
                "detail": s.detail,
            }
            for s in execution.steps
        ])
        query = """
            INSERT INTO remediation_executions (
                plan_id, mode, started_at, finished_at, started_by, result,
                failure_code, changes_sent, pre_run_id, post_run_id, rollback_run_id,
                persist_status, needs_manual_attention, steps_json,
                acknowledged_at, acknowledged_by, acknowledgement_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            execution.plan_id,
            execution.mode.value,
            execution.started_at.isoformat(),
            execution.finished_at.isoformat() if execution.finished_at else None,
            execution.started_by,
            execution.result.value,
            execution.failure_code,
            1 if execution.changes_sent else 0,
            execution.pre_run_id,
            execution.post_run_id,
            execution.rollback_run_id,
            execution.persist_status,
            1 if execution.needs_manual_attention else 0,
            steps_json,
            execution.acknowledged_at.isoformat() if execution.acknowledged_at else None,
            execution.acknowledged_by,
            execution.acknowledgement_note,
        )
        with self._get_conn() as conn:
            with conn:
                cursor = conn.execute(query, params)
                return cursor.lastrowid  # type: ignore[return-value]

    def update_execution(self, execution: RemediationExecution) -> None:
        steps_json = json.dumps([
            {
                "step": s.step,
                "status": s.status,
                "at": s.at.isoformat(),
                "detail": s.detail,
            }
            for s in execution.steps
        ])
        query = """
            UPDATE remediation_executions SET
                finished_at = ?,
                result = ?,
                failure_code = ?,
                changes_sent = ?,
                pre_run_id = ?,
                post_run_id = ?,
                rollback_run_id = ?,
                persist_status = ?,
                needs_manual_attention = ?,
                steps_json = ?,
                acknowledged_at = ?,
                acknowledged_by = ?,
                acknowledgement_note = ?
            WHERE id = ?
        """
        params = (
            execution.finished_at.isoformat() if execution.finished_at else None,
            execution.result.value,
            execution.failure_code,
            1 if execution.changes_sent else 0,
            execution.pre_run_id,
            execution.post_run_id,
            execution.rollback_run_id,
            execution.persist_status,
            1 if execution.needs_manual_attention else 0,
            steps_json,
            execution.acknowledged_at.isoformat() if execution.acknowledged_at else None,
            execution.acknowledged_by,
            execution.acknowledgement_note,
            execution.id,
        )
        with self._get_conn() as conn:
            with conn:
                conn.execute(query, params)

    def get_execution(self, execution_id: int) -> RemediationExecution | None:
        query = "SELECT * FROM remediation_executions WHERE id = ?"
        with self._get_conn() as conn:
            cursor = conn.execute(query, (execution_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_execution(row)

    def list_executions_for_plan(self, plan_id: int) -> list[RemediationExecution]:
        query = "SELECT * FROM remediation_executions WHERE plan_id = ? ORDER BY id DESC"
        with self._get_conn() as conn:
            cursor = conn.execute(query, (plan_id,))
            return [_row_to_execution(r) for r in cursor.fetchall()]

    def get_latest_execution_for_plan(self, plan_id: int) -> RemediationExecution | None:
        query = "SELECT * FROM remediation_executions WHERE plan_id = ? ORDER BY id DESC LIMIT 1"
        with self._get_conn() as conn:
            cursor = conn.execute(query, (plan_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_execution(row)

    def list_attention_executions(self) -> list[tuple[RemediationPlan, RemediationExecution]]:
        query = """
            SELECT
                p.id AS p_id, p.device_id AS p_device_id, p.run_id AS p_run_id,
                p.rule_id AS p_rule_id, p.template_id AS p_template_id,
                p.template_version AS p_template_version, p.risk_level AS p_risk_level,
                p.commands_json AS p_commands_json, p.persist_after_verify AS p_persist_after_verify,
                p.plan_hash AS p_plan_hash, p.status AS p_status, p.proposed_by AS p_proposed_by,
                p.proposed_at AS p_proposed_at, p.decided_by AS p_decided_by,
                p.decided_at AS p_decided_at, p.decision_reason AS p_decision_reason,
                p.approved_plan_hash AS p_approved_plan_hash, p.expires_at AS p_expires_at,
                p.updated_at AS p_updated_at,
                e.*
            FROM remediation_executions e
            JOIN remediation_plans p ON p.id = e.plan_id
            WHERE e.needs_manual_attention = 1 AND e.acknowledged_at IS NULL
            ORDER BY e.started_at DESC
        """
        with self._get_conn() as conn:
            cursor = conn.execute(query)
            results: list[tuple[RemediationPlan, RemediationExecution]] = []
            for row in cursor.fetchall():
                plan = RemediationPlan(
                    id=row["p_id"],
                    device_id=row["p_device_id"],
                    run_id=row["p_run_id"],
                    rule_id=row["p_rule_id"],
                    template_id=row["p_template_id"],
                    template_version=row["p_template_version"],
                    risk_level=RiskLevel(row["p_risk_level"]),
                    commands=tuple(json.loads(row["p_commands_json"])),
                    persist_after_verify=bool(row["p_persist_after_verify"]),
                    plan_hash=row["p_plan_hash"],
                    status=PlanStatus(row["p_status"]),
                    proposed_by=row["p_proposed_by"],
                    proposed_at=datetime.fromisoformat(row["p_proposed_at"]),
                    decided_by=row["p_decided_by"],
                    decided_at=_parse_iso(row["p_decided_at"]),
                    decision_reason=row["p_decision_reason"],
                    approved_plan_hash=row["p_approved_plan_hash"],
                    expires_at=datetime.fromisoformat(row["p_expires_at"]),
                    updated_at=datetime.fromisoformat(row["p_updated_at"]),
                )
                exec_item = _row_to_execution(row)
                results.append((plan, exec_item))
            return results

    def acknowledge_attention(
        self,
        plan_id: int,
        actor: str,
        note: str,
        acknowledged_at: datetime,
    ) -> bool:
        clean_note = note[:200] if note else ""
        query = """
            UPDATE remediation_executions
            SET acknowledged_at = ?, acknowledged_by = ?, acknowledgement_note = ?
            WHERE plan_id = ? AND needs_manual_attention = 1 AND acknowledged_at IS NULL
        """
        with self._get_conn() as conn:
            with conn:
                cursor = conn.execute(query, (acknowledged_at.isoformat(), actor, clean_note, plan_id))
                return cursor.rowcount > 0

    def get_stale_running_executions(self, cutoff: datetime) -> list[RemediationExecution]:
        query = """
            SELECT * FROM remediation_executions
            WHERE result = 'RUNNING' AND started_at <= ?
            ORDER BY started_at ASC
        """
        with self._get_conn() as conn:
            cursor = conn.execute(query, (cutoff.isoformat(),))
            return [_row_to_execution(r) for r in cursor.fetchall()]

