"""Unit tests for AuditRunService (Spec 8.5)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any
import pytest

from app.connectors.fake_connector import FakeConnector
from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.device import Credentials, Device
from app.domain.errors import (
    AuditAlreadyRunningError,
    AuditNotFoundError,
    ConnectionTimeoutError,
    CredentialsRequiredError,
    DeviceNotFoundError,
)
from app.factories.connector_factory import ConnectorFactory
from app.repositories.audit_repository import SqliteAuditRepository
from app.repositories.database import init_db
from app.repositories.device_repository import SqliteDeviceRepository
from app.rules.registry import build_default_engine
from app.services.audit_run_service import AuditRunService
from app.services.audit_service import AuditService

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "configs"


class BlockingFakeConnector(FakeConnector):
    """FakeConnector that pauses in get_running_config until an event is set."""

    def __init__(self, *args: Any, block_event: threading.Event, ready_event: threading.Event, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.block_event = block_event
        self.ready_event = ready_event

    def get_running_config(self) -> str:
        self.ready_event.set()
        self.block_event.wait(timeout=5.0)
        return super().get_running_config()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "test_service.db"
    init_db(p)
    return p


@pytest.fixture
def device_repo(db_path: Path) -> SqliteDeviceRepository:
    return SqliteDeviceRepository(db_path)


@pytest.fixture
def audit_repo(db_path: Path) -> SqliteAuditRepository:
    return SqliteAuditRepository(db_path)


@pytest.fixture
def sample_device(device_repo: SqliteDeviceRepository) -> Device:
    now = datetime.now(timezone.utc)
    dev = Device(
        device_id="R1",
        name="Router 1",
        host="192.168.1.1",
        port=22,
        platform="cisco_ios",
        created_at=now,
        updated_at=now,
    )
    device_repo.add(dev)
    return dev


@pytest.fixture
def credentials() -> Credentials:
    return Credentials(username="admin", password="TestPassword123!")


def test_audit_insecure_config_saved_and_retrieved(
    sample_device: Device,
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
    credentials: Credentials,
):
    cfg_text = (FIXTURES_DIR / "ios_insecure.cfg").read_text(encoding="utf-8")
    fake_conn = FakeConnector(config_text=cfg_text, hostname="R1-INSECURE")

    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())

    service = AuditRunService(device_repo, audit_repo, audit_service)
    detail = service.run_audit("R1", credentials)

    assert detail.summary.status == AuditStatus.COMPLETED
    assert detail.summary.fail_count == 8
    assert detail.summary.pass_count == 0
    assert detail.summary.hostname == "R1-INSECURE"
    assert len(detail.findings) == 8


def test_audit_secure_config_saved_and_retrieved(
    sample_device: Device,
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
    credentials: Credentials,
):
    cfg_text = (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")
    fake_conn = FakeConnector(config_text=cfg_text, hostname="R1-SECURE")

    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())

    service = AuditRunService(device_repo, audit_repo, audit_service)
    detail = service.run_audit("R1", credentials)

    assert detail.summary.status == AuditStatus.COMPLETED
    assert detail.summary.fail_count == 0
    assert detail.summary.pass_count == 8
    assert detail.summary.hostname == "R1-SECURE"
    assert len(detail.findings) == 8


def test_audit_connection_failure_saves_failed_run(
    sample_device: Device,
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
    credentials: Credentials,
):
    fake_conn = FakeConnector(config_text="hostname R1\n", fail_on=ConnectionTimeoutError)

    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())

    service = AuditRunService(device_repo, audit_repo, audit_service)
    detail = service.run_audit("R1", credentials)

    assert detail.summary.status == AuditStatus.FAILED
    assert detail.summary.error_code == "CONNECT_TIMEOUT"
    assert detail.summary.error_message is not None
    assert len(detail.findings) == 0


def test_audit_missing_device_raises_not_found(
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
    credentials: Credentials,
):
    factory = ConnectorFactory()
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())
    service = AuditRunService(device_repo, audit_repo, audit_service)

    with pytest.raises(DeviceNotFoundError, match="not found"):
        service.run_audit("NONEXISTENT", credentials)


def test_audit_missing_credentials_raises_error(
    sample_device: Device,
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
):
    factory = ConnectorFactory()
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())
    # No default_credentials provided and none passed in run_audit
    service = AuditRunService(device_repo, audit_repo, audit_service, default_credentials=None)

    with pytest.raises(CredentialsRequiredError, match="Credentials required"):
        service.run_audit("R1", credentials=None)


def test_audit_uses_default_credentials_when_none_provided(
    sample_device: Device,
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
    credentials: Credentials,
):
    cfg_text = (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")
    fake_conn = FakeConnector(config_text=cfg_text, hostname="R1")

    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: fake_conn)
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())

    service = AuditRunService(
        device_repo,
        audit_repo,
        audit_service,
        default_credentials=lambda: credentials,
    )
    detail = service.run_audit("R1", credentials=None)
    assert detail.summary.status == AuditStatus.COMPLETED


def test_concurrent_audit_same_device_raises_audit_already_running(
    sample_device: Device,
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
    credentials: Credentials,
):
    block_event = threading.Event()
    ready_event = threading.Event()

    cfg_text = (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")
    blocking_conn = BlockingFakeConnector(
        config_text=cfg_text,
        hostname="R1",
        block_event=block_event,
        ready_event=ready_event,
    )

    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: blocking_conn)
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())
    service = AuditRunService(device_repo, audit_repo, audit_service)

    thread_error: list[Exception] = []

    def run_first():
        try:
            service.run_audit("R1", credentials)
        except Exception as e:
            thread_error.append(e)

    t1 = threading.Thread(target=run_first)
    t1.start()

    # Wait until thread 1 has acquired the lock and entered get_running_config
    assert ready_event.wait(timeout=2.0)

    try:
        # Second call on same device must immediately raise AuditAlreadyRunningError
        with pytest.raises(AuditAlreadyRunningError, match="already running"):
            service.run_audit("R1", credentials)
    finally:
        # Unblock thread 1 and join
        block_event.set()
        t1.join(timeout=2.0)

    assert not thread_error


def test_concurrent_audit_different_devices_do_not_block(
    sample_device: Device,
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
    credentials: Credentials,
):
    # Add second device R2
    now = datetime.now(timezone.utc)
    device_repo.add(
        Device("R2", "Router 2", "192.168.1.2", 22, "cisco_ios", now, now)
    )

    block_event = threading.Event()
    ready_event = threading.Event()

    cfg_text = (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")
    blocking_conn = BlockingFakeConnector(
        config_text=cfg_text,
        hostname="R1",
        block_event=block_event,
        ready_event=ready_event,
    )
    normal_conn = FakeConnector(config_text=cfg_text, hostname="R2")

    def make_conn(target, creds):
        if target.device_id == "R1":
            return blocking_conn
        return normal_conn

    factory = ConnectorFactory()
    factory.register("cisco_ios", make_conn)
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())
    service = AuditRunService(device_repo, audit_repo, audit_service)

    t1 = threading.Thread(target=lambda: service.run_audit("R1", credentials))
    t1.start()
    assert ready_event.wait(timeout=2.0)

    try:
        # R2 can run without blocking
        detail2 = service.run_audit("R2", credentials)
        assert detail2.summary.device_id == "R2"
        assert detail2.summary.status == AuditStatus.COMPLETED
    finally:
        block_event.set()
        t1.join(timeout=2.0)


def test_lock_released_on_error(
    sample_device: Device,
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
    credentials: Credentials,
):
    factory = ConnectorFactory()
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())
    service = AuditRunService(device_repo, audit_repo, audit_service)

    # Force an unexpected exception during save_run
    def failing_save_run(result):
        raise RuntimeError("DB disk full error")

    audit_repo.save_run = failing_save_run  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="DB disk full error"):
        service.run_audit("R1", credentials)

    # Device lock should be released; restore save_run and verify lock is available
    del audit_repo.save_run
    cfg_text = (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")
    factory.register("cisco_ios", lambda t, c: FakeConnector(config_text=cfg_text, hostname="R1"))
    detail = service.run_audit("R1", credentials)
    assert detail.summary.status == AuditStatus.COMPLETED


def test_get_run_and_list_runs_and_latest(
    sample_device: Device,
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
    credentials: Credentials,
):
    cfg_text = (FIXTURES_DIR / "ios_secure.cfg").read_text(encoding="utf-8")
    factory = ConnectorFactory()
    factory.register("cisco_ios", lambda t, c: FakeConnector(config_text=cfg_text, hostname="R1"))
    audit_service = AuditService(connector_factory=factory, engine=build_default_engine())
    service = AuditRunService(device_repo, audit_repo, audit_service)

    # Initial state
    assert service.latest_run("R1") is None
    items, total = service.list_runs("R1")
    assert total == 0
    assert items == []

    detail = service.run_audit("R1", credentials)
    run_id = detail.summary.id

    fetched = service.get_run(run_id)
    assert fetched.summary.id == run_id

    latest = service.latest_run("R1")
    assert latest is not None
    assert latest.id == run_id

    items, total = service.list_runs("R1")
    assert total == 1
    assert items[0].id == run_id

    # Nonexistent run
    with pytest.raises(AuditNotFoundError, match="not found"):
        service.get_run(9999)

    # Nonexistent device for list/latest
    with pytest.raises(DeviceNotFoundError):
        service.list_runs("NONEXISTENT")

    with pytest.raises(DeviceNotFoundError):
        service.latest_run("NONEXISTENT")
