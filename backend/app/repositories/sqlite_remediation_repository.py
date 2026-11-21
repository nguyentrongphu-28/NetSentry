"""SQLite implementation of RemediationRepository."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from datetime import datetime
from typing import Any, Generator

from app.domain.entities.remediation import (
    PlanEvent,
    PlanStatus,
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
