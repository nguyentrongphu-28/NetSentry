"""SQLite implementation of DeviceRepository."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.domain.entities.device import Device
from app.domain.errors import DuplicateDeviceError
from app.domain.interfaces.device_repository import DeviceRepository
from app.repositories.database import connect


def _parse_datetime(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _row_to_device(row: sqlite3.Row) -> Device:
    return Device(
        device_id=row["device_id"],
        name=row["name"],
        host=row["host"],
        port=row["port"],
        platform=row["platform"],
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


class SqliteDeviceRepository(DeviceRepository):
    """SQLite-backed DeviceRepository. Each method opens its own connection."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def add(self, device: Device) -> None:
        conn = connect(self._db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO devices
                        (device_id, name, host, port, platform, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device.device_id,
                        device.name,
                        device.host,
                        device.port,
                        device.platform,
                        device.created_at.isoformat(),
                        device.updated_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateDeviceError(
                f"Device '{device.device_id}' or host/port "
                f"({device.host}:{device.port}) already exists",
            ) from exc
        finally:
            conn.close()

    def get(self, device_id: str) -> Device | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT * FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            return _row_to_device(row) if row else None
        finally:
            conn.close()

    def list(self) -> list[Device]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM devices ORDER BY device_id ASC"
            ).fetchall()
            return [_row_to_device(r) for r in rows]
        finally:
            conn.close()

    def delete(self, device_id: str) -> bool:
        conn = connect(self._db_path)
        try:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM devices WHERE device_id = ?", (device_id,)
                )
            return cursor.rowcount > 0
        finally:
            conn.close()
