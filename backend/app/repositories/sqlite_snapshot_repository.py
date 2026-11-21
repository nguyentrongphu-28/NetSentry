from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import ContextManager
from contextlib import contextmanager

from app.domain.entities.snapshot import ConfigSnapshot
from app.domain.interfaces.snapshot_repository import SnapshotRepository
from app.repositories.database import connect


def _parse_datetime(val: str) -> datetime:
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SqliteSnapshotRepository(SnapshotRepository):
    """SQLite-backed metadata store for configuration snapshots."""

    def __init__(self, connection_or_path: sqlite3.Connection | str | Path) -> None:
        if isinstance(connection_or_path, (str, Path)):
            self._db_path: Path | None = Path(connection_or_path)
            self._conn: sqlite3.Connection | None = None
        else:
            self._db_path = None
            self._conn = connection_or_path

    @contextmanager
    def _get_conn(self):
        if self._conn is not None:
            yield self._conn
        else:
            conn = connect(self._db_path)
            try:
                yield conn
            finally:
                conn.close()

    def _row_to_entity(self, row: sqlite3.Row) -> tuple[ConfigSnapshot, str]:
        snapshot = ConfigSnapshot(
            id=row["id"],
            device_id=row["device_id"],
            run_id=row["run_id"],
            created_at=_parse_datetime(row["created_at"]),
            content_sha256=row["content_sha256"],
            size_bytes=row["size_bytes"],
            line_count=row["line_count"],
            redaction_version=row["redaction_version"],
        )
        return snapshot, row["file_name"]

    def save(self, snapshot: ConfigSnapshot, file_name: str) -> ConfigSnapshot:
        with self._get_conn() as conn:
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO config_snapshots (
                        device_id, run_id, created_at, content_sha256,
                        size_bytes, line_count, redaction_version, file_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot.device_id,
                        snapshot.run_id,
                        snapshot.created_at.isoformat(),
                        snapshot.content_sha256,
                        snapshot.size_bytes,
                        snapshot.line_count,
                        snapshot.redaction_version,
                        file_name,
                    ),
                )
                assigned_id = cur.lastrowid
                assert assigned_id is not None
                return ConfigSnapshot(
                    id=assigned_id,
                    device_id=snapshot.device_id,
                    run_id=snapshot.run_id,
                    created_at=snapshot.created_at,
                    content_sha256=snapshot.content_sha256,
                    size_bytes=snapshot.size_bytes,
                    line_count=snapshot.line_count,
                    redaction_version=snapshot.redaction_version,
                )

    def get(self, snapshot_id: int) -> tuple[ConfigSnapshot, str] | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM config_snapshots WHERE id = ?",
                (snapshot_id,),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_entity(row)

    def get_by_run_id(self, run_id: int) -> tuple[ConfigSnapshot, str] | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM config_snapshots WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_entity(row)

    def list_for_device(self, device_id: str, limit: int = 30) -> list[ConfigSnapshot]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM config_snapshots
                WHERE device_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (device_id, limit),
            ).fetchall()
            return [self._row_to_entity(r)[0] for r in rows]

    def delete(self, snapshot_id: int) -> str | None:
        with self._get_conn() as conn:
            with conn:
                row = conn.execute(
                    "SELECT file_name FROM config_snapshots WHERE id = ?",
                    (snapshot_id,),
                ).fetchone()
                if row is None:
                    return None
                file_name = str(row["file_name"])
                conn.execute("DELETE FROM config_snapshots WHERE id = ?", (snapshot_id,))
                return file_name

    def delete_for_device(self, device_id: str) -> list[str]:
        with self._get_conn() as conn:
            with conn:
                rows = conn.execute(
                    "SELECT file_name FROM config_snapshots WHERE device_id = ?",
                    (device_id,),
                ).fetchall()
                file_names = [str(r["file_name"]) for r in rows]
                conn.execute("DELETE FROM config_snapshots WHERE device_id = ?", (device_id,))
                return file_names

    def enforce_retention(
        self, device_id: str, keep: int, excluded_snapshot_ids: set[int] | None = None
    ) -> list[str]:
        if keep < 1:
            keep = 1
        with self._get_conn() as conn:
            with conn:
                excluded = excluded_snapshot_ids or set()
                # Select candidate snapshots for device ordered DESC
                rows = conn.execute(
                    """
                    SELECT id, file_name FROM config_snapshots
                    WHERE device_id = ?
                    ORDER BY created_at DESC
                    """,
                    (device_id,),
                ).fetchall()

                # Filter out excluded snapshots from retention counting
                retained_count = 0
                to_delete: list[tuple[int, str]] = []

                for r in rows:
                    snap_id = r["id"]
                    file_name = str(r["file_name"])
                    if snap_id in excluded:
                        # Pinned snapshot is never deleted and does not count towards keep limit
                        continue

                    retained_count += 1
                    if retained_count > keep:
                        to_delete.append((snap_id, file_name))

                if not to_delete:
                    return []

                ids_to_delete = [item[0] for item in to_delete]
                file_names = [item[1] for item in to_delete]
                placeholders = ",".join("?" for _ in ids_to_delete)
                conn.execute(
                    f"DELETE FROM config_snapshots WHERE id IN ({placeholders})",
                    ids_to_delete,
                )
                return file_names

    def list_all_file_names(self) -> set[str]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT file_name FROM config_snapshots").fetchall()
            return {str(r["file_name"]) for r in rows}
