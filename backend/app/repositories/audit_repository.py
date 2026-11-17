"""SQLite implementation of AuditRepository."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

from app.domain.entities.audit_result import AuditResult, AuditStatus
from app.domain.entities.audit_run import AuditRunDetail, AuditRunSummary
from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.errors import DeviceNotFoundError
from app.domain.interfaces.audit_repository import AuditRepository
from app.repositories.database import connect


def _parse_datetime(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _row_to_summary(row: sqlite3.Row) -> AuditRunSummary:
    return AuditRunSummary(
        id=row["id"],
        device_id=row["device_id"],
        platform=row["platform"],
        status=AuditStatus(row["status"]),
        started_at=_parse_datetime(row["started_at"]),
        finished_at=_parse_datetime(row["finished_at"]),
        hostname=row["hostname"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        pass_count=row["pass_count"],
        fail_count=row["fail_count"],
        unknown_count=row["unknown_count"],
    )


class SqliteAuditRepository(AuditRepository):
    """SQLite-backed AuditRepository. Each method opens its own connection."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def save_run(self, result: AuditResult) -> int:
        conn = connect(self._db_path)
        try:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO audit_runs (
                        device_id, platform, status, started_at, finished_at,
                        hostname, error_code, error_message,
                        pass_count, fail_count, unknown_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.device_id,
                        result.platform,
                        str(result.status),
                        result.started_at.isoformat(),
                        result.finished_at.isoformat(),
                        result.hostname,
                        result.error_code,
                        result.error_message,
                        result.pass_count,
                        result.fail_count,
                        result.unknown_count,
                    ),
                )
                run_id: int = cursor.lastrowid  # type: ignore[assignment]

                for f in result.findings:
                    conn.execute(
                        """
                        INSERT INTO findings (
                            audit_run_id, rule_id, title, severity, status,
                            evidence_json, rationale, remediation, verification, checked_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            f.rule_id,
                            f.title,
                            str(f.severity),
                            str(f.status),
                            json.dumps(list(f.evidence)),
                            f.rationale,
                            f.remediation,
                            f.verification,
                            f.checked_at.isoformat() if f.checked_at is not None else None,
                        ),
                    )
            return run_id
        except sqlite3.IntegrityError as exc:
            raise DeviceNotFoundError(
                f"Device '{result.device_id}' does not exist in repository"
            ) from exc
        finally:
            conn.close()

    def get_run(self, run_id: int) -> AuditRunDetail | None:
        conn = connect(self._db_path)
        try:
            run_row = conn.execute(
                "SELECT * FROM audit_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if run_row is None:
                return None

            summary = _row_to_summary(run_row)

            finding_rows = conn.execute(
                "SELECT * FROM findings WHERE audit_run_id = ? ORDER BY rule_id ASC",
                (run_id,),
            ).fetchall()

            findings: list[Finding] = []
            for f_row in finding_rows:
                findings.append(
                    Finding(
                        rule_id=f_row["rule_id"],
                        title=f_row["title"],
                        severity=Severity(f_row["severity"]),
                        status=FindingStatus(f_row["status"]),
                        evidence=tuple(json.loads(f_row["evidence_json"])),
                        rationale=f_row["rationale"],
                        remediation=f_row["remediation"],
                        verification=f_row["verification"],
                        device_id=summary.device_id,
                        checked_at=_parse_datetime(f_row["checked_at"])
                        if f_row["checked_at"] is not None
                        else None,
                    )
                )

            return AuditRunDetail(summary=summary, findings=tuple(findings))
        finally:
            conn.close()

    def list_runs(
        self, device_id: str, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[AuditRunSummary], int]:
        clamped_limit = max(1, min(limit, 200))
        clamped_offset = max(0, offset)

        conn = connect(self._db_path)
        try:
            total: int = conn.execute(
                "SELECT count(*) FROM audit_runs WHERE device_id = ?",
                (device_id,),
            ).fetchone()[0]

            rows = conn.execute(
                """
                SELECT * FROM audit_runs
                WHERE device_id = ?
                ORDER BY started_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (device_id, clamped_limit, clamped_offset),
            ).fetchall()

            items = [_row_to_summary(r) for r in rows]
            return items, total
        finally:
            conn.close()

    def latest_run(self, device_id: str) -> AuditRunSummary | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                """
                SELECT * FROM audit_runs
                WHERE device_id = ?
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """,
                (device_id,),
            ).fetchone()
            return _row_to_summary(row) if row is not None else None
        finally:
            conn.close()
