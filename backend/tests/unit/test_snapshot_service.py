from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest
import sqlite3

from app.connectors.fake_connector import FakeConnector
from app.domain.entities.audit_result import AuditResult, AuditStatus
from app.domain.entities.device import Credentials, Device, DeviceTarget
from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.errors import ConnectionFailedError
from app.domain.interfaces.device_connector import DeviceConnector
from app.factories.connector_factory import ConnectorFactory
from app.repositories.audit_repository import SqliteAuditRepository
from app.repositories.database import init_db, connect
from app.repositories.device_repository import SqliteDeviceRepository
from app.repositories.file_snapshot_store import FileSnapshotStore
from app.repositories.sqlite_snapshot_repository import SqliteSnapshotRepository
from app.rules.engine import RuleEngine
from app.rules.ios_config_parser import IosConfigParser
from app.security.config_redactor import ConfigRedactor
from app.services.audit_run_service import AuditRunService
from app.services.audit_service import AuditService
from app.services.snapshot_service import SnapshotService


class MockConnectorFactory(ConnectorFactory):
    def __init__(self, config: str, fails: bool = False):
        self.config = config
        self.fails = fails

    def create(self, target: DeviceTarget, credentials: Credentials) -> DeviceConnector:
        return FakeConnector(
            config_text=self.config,
            fail_on=ConnectionFailedError if self.fails else None,
        )


@pytest.fixture
def snapshot_env(tmp_path: Path):
    db_file = tmp_path / "test.db"
    snap_dir = tmp_path / "snapshots"
    init_db(db_file)
    conn = connect(db_file)

    device_repo = SqliteDeviceRepository(db_file)
    audit_repo = SqliteAuditRepository(db_file)
    snap_repo = SqliteSnapshotRepository(conn)
    file_store = FileSnapshotStore(snap_dir)
    redactor = ConfigRedactor(hmac_key=b"test-hmac-key")

    snap_service = SnapshotService(
        snapshot_repository=snap_repo,
        file_store=file_store,
        redactor=redactor,
        enabled=True,
        keep=5,
    )

    now = datetime.now(timezone.utc)
    device = Device(
        device_id="dev-test",
        name="Test Switch",
        host="192.168.1.1",
        port=22,
        platform="cisco_ios",
        created_at=now,
        updated_at=now,
    )
    device_repo.add(device)

    return {
        "conn": conn,
        "device_repo": device_repo,
        "audit_repo": audit_repo,
        "snap_repo": snap_repo,
        "file_store": file_store,
        "snap_service": snap_service,
        "snap_dir": snap_dir,
    }


def test_audit_completed_creates_snapshot_with_no_sentinels(snapshot_env):
    raw_cfg = (
        "hostname Lab-R1\n"
        "enable secret 5 SENTINEL_ENABLE_SEC\n"
        "snmp-server community SENTINEL_COMMUNITY RO\n"
        "!\n"
    )
    engine = RuleEngine(rules=[], parser=IosConfigParser())
    factory = MockConnectorFactory(config=raw_cfg, fails=False)
    audit_service = AuditService(factory, engine)
    run_service = AuditRunService(
        snapshot_env["device_repo"],
        snapshot_env["audit_repo"],
        audit_service,
        snapshot_service=snapshot_env["snap_service"],
    )

    creds = Credentials(username="admin", password="password")
    detail = run_service.run_audit("dev-test", creds)

    assert detail.summary.status == AuditStatus.COMPLETED
    run_id = detail.summary.id

    # Verify snapshot was created
    snapshots = snapshot_env["snap_service"].list_for_device("dev-test")
    assert len(snapshots) == 1
    assert snapshots[0].run_id == run_id

    # Verify content was redacted and stored
    snap, content = snapshot_env["snap_service"].read_content(snapshots[0].id)
    assert "SENTINEL_" not in content
    assert "<REDACTED:" in content

    # Scan entire snapshot directory: no raw sentinels must exist on disk!
    snap_dir = snapshot_env["snap_dir"]
    for path in snap_dir.rglob("*.cfg"):
        assert "SENTINEL_" not in path.read_text(encoding="utf-8")


def test_audit_failed_does_not_create_snapshot(snapshot_env):
    engine = RuleEngine(rules=[], parser=IosConfigParser())
    factory = MockConnectorFactory(config="", fails=True)
    audit_service = AuditService(factory, engine)
    run_service = AuditRunService(
        snapshot_env["device_repo"],
        snapshot_env["audit_repo"],
        audit_service,
        snapshot_service=snapshot_env["snap_service"],
    )

    creds = Credentials(username="admin", password="password")
    detail = run_service.run_audit("dev-test", creds)

    assert detail.summary.status == AuditStatus.FAILED
    assert len(snapshot_env["snap_service"].list_for_device("dev-test")) == 0


def test_snapshot_failure_does_not_fail_audit(snapshot_env, monkeypatch):
    raw_cfg = "hostname Lab-R1\n"
    engine = RuleEngine(rules=[], parser=IosConfigParser())
    factory = MockConnectorFactory(config=raw_cfg, fails=False)
    audit_service = AuditService(factory, engine)

    # Force snapshot service to fail
    def _exploding_create(*args, **kwargs):
        raise OSError("Disk full simulation")

    monkeypatch.setattr(snapshot_env["snap_service"], "create_for_run", _exploding_create)

    run_service = AuditRunService(
        snapshot_env["device_repo"],
        snapshot_env["audit_repo"],
        audit_service,
        snapshot_service=snapshot_env["snap_service"],
    )

    creds = Credentials(username="admin", password="password")
    detail = run_service.run_audit("dev-test", creds)

    # Audit must still succeed even if snapshot creation failed!
    assert detail.summary.status == AuditStatus.COMPLETED


def test_snapshot_disabled_creates_nothing(snapshot_env):
    snapshot_env["snap_service"].enabled = False
    raw_cfg = "hostname Lab-R1\n"
    engine = RuleEngine(rules=[], parser=IosConfigParser())
    factory = MockConnectorFactory(config=raw_cfg, fails=False)
    audit_service = AuditService(factory, engine)

    run_service = AuditRunService(
        snapshot_env["device_repo"],
        snapshot_env["audit_repo"],
        audit_service,
        snapshot_service=snapshot_env["snap_service"],
    )

    creds = Credentials(username="admin", password="password")
    detail = run_service.run_audit("dev-test", creds)

    assert detail.summary.status == AuditStatus.COMPLETED
    assert len(snapshot_env["snap_service"].list_for_device("dev-test")) == 0
