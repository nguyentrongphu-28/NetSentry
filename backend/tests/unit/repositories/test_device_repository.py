"""Unit tests for SqliteDeviceRepository (Spec 8.2)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.domain.entities.device import Device
from app.domain.errors import DuplicateDeviceError
from app.repositories.database import connect, init_db
from app.repositories.device_repository import SqliteDeviceRepository


@pytest.fixture
def repo(tmp_path: Path) -> SqliteDeviceRepository:
    db_file = tmp_path / "devices.db"
    init_db(db_file)
    return SqliteDeviceRepository(db_file)


def _make_device(
    device_id: str = "R1",
    name: str = "Router 1",
    host: str = "192.168.1.1",
    port: int = 22,
    platform: str = "cisco_ios",
) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        name=name,
        host=host,
        port=port,
        platform=platform,
        created_at=now,
        updated_at=now,
    )


def test_add_and_get_device(repo: SqliteDeviceRepository):
    device = _make_device(device_id="R1", name="Core Router", host="10.0.0.1", port=22)
    repo.add(device)

    retrieved = repo.get("R1")
    assert retrieved is not None
    assert retrieved.device_id == "R1"
    assert retrieved.name == "Core Router"
    assert retrieved.host == "10.0.0.1"
    assert retrieved.port == 22
    assert retrieved.platform == "cisco_ios"
    assert retrieved.created_at == device.created_at
    assert retrieved.updated_at == device.updated_at


def test_get_nonexistent_device_returns_none(repo: SqliteDeviceRepository):
    assert repo.get("NONEXISTENT") is None


def test_duplicate_device_id_raises_error(repo: SqliteDeviceRepository):
    dev1 = _make_device(device_id="R1", host="10.0.0.1", port=22)
    dev2 = _make_device(device_id="R1", host="10.0.0.2", port=22)
    repo.add(dev1)

    with pytest.raises(DuplicateDeviceError, match="already exists"):
        repo.add(dev2)


def test_duplicate_host_port_raises_error(repo: SqliteDeviceRepository):
    dev1 = _make_device(device_id="R1", host="10.0.0.1", port=22)
    dev2 = _make_device(device_id="R2", host="10.0.0.1", port=22)
    repo.add(dev1)

    with pytest.raises(DuplicateDeviceError, match="already exists"):
        repo.add(dev2)


def test_list_devices_sorted_by_device_id(repo: SqliteDeviceRepository):
    repo.add(_make_device(device_id="R3", host="10.0.0.3", port=22))
    repo.add(_make_device(device_id="R1", host="10.0.0.1", port=22))
    repo.add(_make_device(device_id="R2", host="10.0.0.2", port=22))

    devices = repo.list()
    assert len(devices) == 3
    assert [d.device_id for d in devices] == ["R1", "R2", "R3"]


def test_delete_device(repo: SqliteDeviceRepository):
    device = _make_device(device_id="R1")
    repo.add(device)
    assert repo.get("R1") is not None

    deleted = repo.delete("R1")
    assert deleted is True
    assert repo.get("R1") is None

    # Deleting again returns False
    assert repo.delete("R1") is False


def test_delete_cascades_audit_runs_and_findings(repo: SqliteDeviceRepository, tmp_path: Path):
    db_file = tmp_path / "devices.db"
    device = _make_device(device_id="R1")
    repo.add(device)

    # Directly insert an audit_run and finding linked to R1
    conn = connect(db_file)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_runs
                    (device_id, platform, status, started_at, finished_at, pass_count, fail_count, unknown_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("R1", "cisco_ios", "COMPLETED", "2026-11-17T00:00:00Z", "2026-11-17T00:01:00Z", 1, 0, 0),
            )
            run_id = cursor.lastrowid
            conn.execute(
                """
                INSERT INTO findings
                    (audit_run_id, rule_id, title, severity, status, evidence_json, rationale, remediation, verification)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, "SEC-01", "Title", "HIGH", "PASS", "[]", "Rat", "Rem", "Ver"),
            )
    finally:
        conn.close()

    # Verify rows exist before deletion
    conn = connect(db_file)
    try:
        assert conn.execute("SELECT count(*) FROM audit_runs WHERE device_id = 'R1'").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM findings").fetchone()[0] == 1
    finally:
        conn.close()

    # Delete device
    assert repo.delete("R1") is True

    # Verify cascaded deletion
    conn = connect(db_file)
    try:
        assert conn.execute("SELECT count(*) FROM devices WHERE device_id = 'R1'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM audit_runs WHERE device_id = 'R1'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM findings").fetchone()[0] == 0
    finally:
        conn.close()


def test_sql_injection_safe(repo: SqliteDeviceRepository, tmp_path: Path):
    malicious_id = "x'; DROP TABLE devices;--"
    device = _make_device(device_id=malicious_id, host="10.0.0.99")
    repo.add(device)

    retrieved = repo.get(malicious_id)
    assert retrieved is not None
    assert retrieved.device_id == malicious_id

    # Verify devices table still exists and is intact
    db_file = tmp_path / "devices.db"
    conn = connect(db_file)
    try:
        row = conn.execute("SELECT count(*) FROM devices").fetchone()
        assert row[0] == 1
    finally:
        conn.close()
