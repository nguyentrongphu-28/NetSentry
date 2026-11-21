from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from app.domain.entities.snapshot import ConfigSnapshot
from app.domain.interfaces.snapshot_repository import SnapshotRepository


def _parse_datetime(val: str) -> datetime:
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SqliteSnapshotRepository(SnapshotRepository):
    """SQLite-backed metadata store for configuration snapshots."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

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
        with self._conn:
            cur = self._conn.execute(
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
        row = self._conn.execute(
            "SELECT * FROM config_snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    def get_by_run_id(self, run_id: int) -> tuple[ConfigSnapshot, str] | None:
        row = self._conn.execute(
            "SELECT * FROM config_snapshots WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    def list_for_device(self, device_id: str, limit: int = 30) -> list[ConfigSnapshot]:
        rows = self._conn.execute(
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
        with self._conn:
            row = self._conn.execute(
                "SELECT file_name FROM config_snapshots WHERE id = ?",
                (snapshot_id,),
            ).fetchone()
            if row is None:
                return None
            file_name = str(row["file_name"])
            self._conn.execute("DELETE FROM config_snapshots WHERE id = ?", (snapshot_id,))
            return file_name

    def delete_for_device(self, device_id: str) -> list[str]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT file_name FROM config_snapshots WHERE device_id = ?",
                (device_id,),
            ).fetchall()
            file_names = [str(r["file_name"]) for r in rows]
            self._conn.execute("DELETE FROM config_snapshots WHERE device_id = ?", (device_id,))
            return file_names

    def enforce_retention(self, device_id: str, keep: int) -> list[str]:
        if keep < 1:
            keep = 1
        with self._conn:
            # Find IDs of snapshots beyond the `keep` newest ones
            rows = self._conn.execute(
                """
                SELECT id, file_name FROM config_snapshots
                WHERE device_id = ?
                ORDER BY created_at DESC
                LIMIT -1 OFFSET ?
                """,
                (device_id, keep),
            ).fetchall()
            if not rows:
                return []
            ids_to_delete = [r["id"] for r in rows]
            file_names = [str(r["file_name"]) for r in rows]
            placeholders = ",".join("?" for _ in ids_to_delete)
            self._conn.execute(
                f"DELETE FROM config_snapshots WHERE id IN ({placeholders})",
                ids_to_delete,
            )
            return file_names

    def list_all_file_names(self) -> set[str]:
        rows = self._conn.execute("SELECT file_name FROM config_snapshots").fetchall()
        return {str(r["file_name"]) for r in rows}
