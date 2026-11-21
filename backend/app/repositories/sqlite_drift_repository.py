"""SQLite repository for Drift Results."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator
import sqlite3

from app.domain.entities.drift import DriftSummary
from app.repositories.database import connect


class SqliteDriftRepository:
    """SQLite-backed repository for audit run drift results."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = connect(self._db_path)
        try:
            yield conn
        finally:
            conn.close()

    def save_summary(
        self,
        *,
        run_id: int,
        device_id: str,
        baseline_id: int,
        checked_at: str,
        summary: DriftSummary,
    ) -> None:
        with self._get_conn() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO drift_results (
                        run_id, device_id, baseline_id, checked_at,
                        status, added_blocks, removed_blocks, changed_blocks,
                        security_relevant_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        device_id,
                        baseline_id,
                        checked_at,
                        summary.status,
                        summary.added_blocks,
                        summary.removed_blocks,
                        summary.changed_blocks,
                        summary.security_relevant_count,
                    ),
                )

    def get_by_run(self, run_id: int) -> tuple[int, DriftSummary] | None:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM drift_results WHERE run_id = ?",
                (run_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            summary = DriftSummary(
                status=row["status"],
                added_blocks=row["added_blocks"],
                removed_blocks=row["removed_blocks"],
                changed_blocks=row["changed_blocks"],
                security_relevant_count=row["security_relevant_count"],
            )
            return (row["baseline_id"], summary)

    def list_history(self, device_id: str, limit: int = 30) -> list[dict[str, object]]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT run_id, device_id, baseline_id, checked_at,
                       status, added_blocks, removed_blocks, changed_blocks,
                       security_relevant_count
                FROM drift_results
                WHERE device_id = ?
                ORDER BY checked_at DESC, run_id DESC
                LIMIT ?
                """,
                (device_id, limit),
            )
            results: list[dict[str, object]] = []
            for row in cursor.fetchall():
                results.append({
                    "run_id": row["run_id"],
                    "device_id": row["device_id"],
                    "baseline_id": row["baseline_id"],
                    "checked_at": row["checked_at"],
                    "status": row["status"],
                    "added_blocks": row["added_blocks"],
                    "removed_blocks": row["removed_blocks"],
                    "changed_blocks": row["changed_blocks"],
                    "security_relevant_count": row["security_relevant_count"],
                })
            return results
