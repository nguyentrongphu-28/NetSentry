"""Unit tests for SqliteAuditRepository (Spec 8.3)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.domain.entities.audit_result import AuditResult, AuditStatus
from app.domain.entities.device import Device
from app.domain.entities.finding import Finding, FindingStatus, Severity
from app.domain.errors import DeviceNotFoundError
from app.repositories.audit_repository import SqliteAuditRepository
from app.repositories.database import connect, init_db
from app.repositories.device_repository import SqliteDeviceRepository


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "test_audit.db"
    init_db(p)
    return p


@pytest.fixture
def device_repo(db_path: Path) -> SqliteDeviceRepository:
    return SqliteDeviceRepository(db_path)


@pytest.fixture
def audit_repo(db_path: Path) -> SqliteAuditRepository:
    return SqliteAuditRepository(db_path)


def _seed_device(
    device_repo: SqliteDeviceRepository,
    device_id: str = "R1",
    host: str | None = None,
) -> Device:
    now = datetime.now(timezone.utc)
    dev = Device(
        device_id=device_id,
        name=f"Device {device_id}",
        host=host or f"192.168.1.{sum(ord(c) for c in device_id) % 250 + 1}",
        port=22,
        platform="cisco_ios",
        created_at=now,
        updated_at=now,
    )
    device_repo.add(dev)
    return dev


def _make_finding(
    rule_id: str,
    title: str = "Test Rule",
    severity: Severity = Severity.HIGH,
    status: FindingStatus = FindingStatus.FAIL,
    evidence: tuple[str, ...] = ("line 1", "line 2"),
    checked_at: datetime | None = None,
    device_id: str = "R1",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        title=title,
        severity=severity,
        status=status,
        evidence=evidence,
        rationale="Rationale text",
        remediation="Remediation text",
        verification="Verification text",
        device_id=device_id,
        checked_at=checked_at,
    )


def test_save_and_get_run_roundtrip_8_findings(
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
):
    _seed_device(device_repo, "R1")

    now = datetime(2026, 11, 17, 5, 0, 0, tzinfo=timezone.utc)
    checked_at = datetime(2026, 11, 17, 5, 0, 1, tzinfo=timezone.utc)

    findings = tuple(
        _make_finding(
            rule_id=f"RULE-{i:02d}",
            title=f"Rule Title {i}",
            severity=Severity.HIGH if i % 2 == 0 else Severity.MEDIUM,
            status=FindingStatus.PASS if i % 2 == 0 else FindingStatus.FAIL,
            evidence=(f"evidence {i}a", f"evidence {i}b"),
            checked_at=checked_at,
            device_id="R1",
        )
        for i in range(1, 9)
    )

    result = AuditResult(
        device_id="R1",
        platform="cisco_ios",
        status=AuditStatus.COMPLETED,
        started_at=now,
        finished_at=now,
        findings=findings,
        hostname="Router-R1",
    )

    run_id = audit_repo.save_run(result)
    assert run_id > 0

    detail = audit_repo.get_run(run_id)
    assert detail is not None
    assert detail.summary.id == run_id
    assert detail.summary.device_id == "R1"
    assert detail.summary.platform == "cisco_ios"
    assert detail.summary.status == AuditStatus.COMPLETED
    assert detail.summary.started_at == now
    assert detail.summary.finished_at == now
    assert detail.summary.hostname == "Router-R1"
    assert detail.summary.error_code is None
    assert detail.summary.error_message is None
    assert detail.summary.pass_count == 4
    assert detail.summary.fail_count == 4
    assert detail.summary.unknown_count == 0

    assert len(detail.findings) == 8
    for original, retrieved in zip(findings, detail.findings, strict=True):
        assert original == retrieved
        assert isinstance(retrieved.evidence, tuple)
        assert isinstance(retrieved.severity, Severity)
        assert isinstance(retrieved.status, FindingStatus)
        assert retrieved.checked_at == checked_at


def test_save_failed_run_with_no_findings(
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
):
    _seed_device(device_repo, "R1")

    now = datetime(2026, 11, 17, 5, 10, 0, tzinfo=timezone.utc)
    result = AuditResult(
        device_id="R1",
        platform="cisco_ios",
        status=AuditStatus.FAILED,
        started_at=now,
        finished_at=now,
        findings=(),
        hostname=None,
        error_code="CONNECTION_ERROR",
        error_message="SSH timed out after 10s",
    )

    run_id = audit_repo.save_run(result)
    detail = audit_repo.get_run(run_id)
    assert detail is not None
    assert detail.summary.status == AuditStatus.FAILED
    assert detail.summary.error_code == "CONNECTION_ERROR"
    assert detail.summary.error_message == "SSH timed out after 10s"
    assert detail.summary.pass_count == 0
    assert detail.summary.fail_count == 0
    assert detail.summary.unknown_count == 0
    assert len(detail.findings) == 0


def test_get_run_nonexistent_returns_none(audit_repo: SqliteAuditRepository):
    assert audit_repo.get_run(9999) is None


def test_save_run_nonexistent_device_raises_error_and_rolls_back(
    audit_repo: SqliteAuditRepository,
    db_path: Path,
):
    now = datetime.now(timezone.utc)
    result = AuditResult(
        device_id="GHOST_DEVICE",
        platform="cisco_ios",
        status=AuditStatus.COMPLETED,
        started_at=now,
        finished_at=now,
        findings=(_make_finding("RULE-01", device_id="GHOST_DEVICE"),),
    )

    with pytest.raises(DeviceNotFoundError, match="does not exist"):
        audit_repo.save_run(result)

    # Verify atomic rollback: no partial records in audit_runs or findings
    conn = connect(db_path)
    try:
        assert conn.execute("SELECT count(*) FROM audit_runs").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM findings").fetchone()[0] == 0
    finally:
        conn.close()


def test_list_runs_order_and_pagination(
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
):
    _seed_device(device_repo, "R1")

    # Save 5 runs with distinct timestamps
    for i in range(1, 6):
        t = datetime(2026, 11, 17, 1, i, 0, tzinfo=timezone.utc)
        audit_repo.save_run(
            AuditResult(
                device_id="R1",
                platform="cisco_ios",
                status=AuditStatus.COMPLETED,
                started_at=t,
                finished_at=t,
            )
        )

    # list_runs default (newest first)
    items, total = audit_repo.list_runs("R1", limit=3, offset=0)
    assert total == 5
    assert len(items) == 3
    # Newest should be minute 5, then 4, then 3
    assert items[0].started_at == datetime(2026, 11, 17, 1, 5, 0, tzinfo=timezone.utc)
    assert items[1].started_at == datetime(2026, 11, 17, 1, 4, 0, tzinfo=timezone.utc)
    assert items[2].started_at == datetime(2026, 11, 17, 1, 3, 0, tzinfo=timezone.utc)

    # Offset 3 (minute 2 and minute 1)
    items_page2, total_page2 = audit_repo.list_runs("R1", limit=3, offset=3)
    assert total_page2 == 5
    assert len(items_page2) == 2
    assert items_page2[0].started_at == datetime(2026, 11, 17, 1, 2, 0, tzinfo=timezone.utc)
    assert items_page2[1].started_at == datetime(2026, 11, 17, 1, 1, 0, tzinfo=timezone.utc)


def test_list_runs_limit_clamped_to_200(
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
):
    _seed_device(device_repo, "R1")

    # Request limit=500, verify query works and does not fail
    items, total = audit_repo.list_runs("R1", limit=500)
    assert total == 0
    assert len(items) == 0


def test_latest_run(
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
):
    _seed_device(device_repo, "R1")
    _seed_device(device_repo, "R2")

    assert audit_repo.latest_run("R1") is None

    t1 = datetime(2026, 11, 17, 1, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 17, 2, 0, 0, tzinfo=timezone.utc)

    audit_repo.save_run(
        AuditResult(
            device_id="R1",
            platform="cisco_ios",
            status=AuditStatus.COMPLETED,
            started_at=t1,
            finished_at=t1,
            hostname="R1-old",
        )
    )
    audit_repo.save_run(
        AuditResult(
            device_id="R1",
            platform="cisco_ios",
            status=AuditStatus.COMPLETED,
            started_at=t2,
            finished_at=t2,
            hostname="R1-new",
        )
    )

    latest = audit_repo.latest_run("R1")
    assert latest is not None
    assert latest.started_at == t2
    assert latest.hostname == "R1-new"

    # R2 still has None
    assert audit_repo.latest_run("R2") is None


def test_findings_sorted_by_rule_id(
    device_repo: SqliteDeviceRepository,
    audit_repo: SqliteAuditRepository,
):
    _seed_device(device_repo, "R1")
    now = datetime.now(timezone.utc)

    # Insert findings in reverse order
    findings = (
        _make_finding("RULE-03"),
        _make_finding("RULE-01"),
        _make_finding("RULE-02"),
    )
    run_id = audit_repo.save_run(
        AuditResult(
            device_id="R1",
            platform="cisco_ios",
            status=AuditStatus.COMPLETED,
            started_at=now,
            finished_at=now,
            findings=findings,
        )
    )

    detail = audit_repo.get_run(run_id)
    assert detail is not None
    assert [f.rule_id for f in detail.findings] == ["RULE-01", "RULE-02", "RULE-03"]
