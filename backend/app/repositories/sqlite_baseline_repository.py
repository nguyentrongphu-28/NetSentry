"""SQLite repository for Baselines."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
import sqlite3

from app.domain.entities.baseline import Baseline, BaselineStatus
from app.repositories.database import connect


class SqliteBaselineRepository:
    """SQLite-backed repository for approved configuration baselines."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = connect(self._db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _row_to_entity(self, row: sqlite3.Row) -> Baseline:
        approved_at_str = row["approved_at"]
        retired_at_str = row["retired_at"]
        return Baseline(
            id=row["id"],
            device_id=row["device_id"],
            snapshot_id=row["snapshot_id"],
            content_sha256=row["content_sha256"],
            status=BaselineStatus(row["status"]),
            approved_by=row["approved_by"],
            approved_at=datetime.fromisoformat(approved_at_str),
            note=row["note"],
            fail_count_at_approval=row["fail_count_at_approval"],
            retired_at=datetime.fromisoformat(retired_at_str) if retired_at_str else None,
            retired_by=row["retired_by"],
        )

    def get_active(self, device_id: str) -> Baseline | None:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM baselines
                WHERE device_id = ? AND status = 'ACTIVE'
                LIMIT 1
                """,
                (device_id,),
            )
            row = cursor.fetchone()
            return self._row_to_entity(row) if row else None

    def list_history(self, device_id: str, limit: int = 50) -> list[Baseline]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM baselines
                WHERE device_id = ?
                ORDER BY approved_at DESC, id DESC
                LIMIT ?
                """,
                (device_id, limit),
            )
            return [self._row_to_entity(row) for row in cursor.fetchall()]

    def get_by_id(self, baseline_id: int) -> Baseline | None:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM baselines WHERE id = ?",
                (baseline_id,),
            )
            row = cursor.fetchone()
            return self._row_to_entity(row) if row else None

    def is_snapshot_pinned(self, snapshot_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM baselines
                WHERE snapshot_id = ? AND status = 'ACTIVE'
                LIMIT 1
                """,
                (snapshot_id,),
            )
            return cursor.fetchone() is not None

    def set_active_baseline(
        self,
        *,
        device_id: str,
        snapshot_id: int,
        content_sha256: str,
        approved_by: str,
        note: str | None,
        fail_count_at_approval: int,
    ) -> Baseline:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            with conn:
                # 1. Retire existing active baseline
                conn.execute(
                    """
                    UPDATE baselines
                    SET status = 'RETIRED', retired_at = ?, retired_by = ?
                    WHERE device_id = ? AND status = 'ACTIVE'
                    """,
                    (now_iso, approved_by, device_id),
                )

                # 2. Insert new active baseline
                cursor = conn.execute(
                    """
                    INSERT INTO baselines (
                        device_id, snapshot_id, content_sha256, status,
                        approved_by, approved_at, note, fail_count_at_approval
                    )
                    VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?)
                    """,
                    (
                        device_id,
                        snapshot_id,
                        content_sha256,
                        approved_by,
                        now_iso,
                        note,
                        fail_count_at_approval,
                    ),
                )
                new_id = cursor.lastrowid
                row = conn.execute("SELECT * FROM baselines WHERE id = ?", (new_id,)).fetchone()
                return self._row_to_entity(row)

    def retire_active(self, device_id: str, retired_by: str) -> Baseline | None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            with conn:
                row = conn.execute(
                    "SELECT id FROM baselines WHERE device_id = ? AND status = 'ACTIVE'",
                    (device_id,),
                ).fetchone()
                if not row:
                    return None

                baseline_id = row["id"]
                conn.execute(
                    """
                    UPDATE baselines
                    SET status = 'RETIRED', retired_at = ?, retired_by = ?
                    WHERE id = ?
                    """,
                    (now_iso, retired_by, baseline_id),
                )
                updated_row = conn.execute(
                    "SELECT * FROM baselines WHERE id = ?", (baseline_id,)
                ).fetchone()
                return self._row_to_entity(updated_row)
