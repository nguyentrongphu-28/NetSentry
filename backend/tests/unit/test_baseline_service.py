"""Unit tests for BaselineService and snapshot pinning (Spec 9.4 & 9.5)."""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.audit_run import AuditRunSummary
from app.domain.entities.baseline import BaselineStatus
from app.domain.entities.snapshot import ConfigSnapshot
from app.domain.errors import (
    BaselineFailuresNotConfirmedError,
    BaselineNotFoundError,
    DiffInputError,
    SnapshotInUseError,
)
from app.repositories.database import init_db
from app.repositories.file_snapshot_store import FileSnapshotStore
from app.repositories.sqlite_baseline_repository import SqliteBaselineRepository
from app.repositories.sqlite_drift_repository import SqliteDriftRepository
from app.repositories.sqlite_snapshot_repository import SqliteSnapshotRepository
from app.security.config_redactor import ConfigRedactor
from app.services.baseline_service import BaselineService
from app.services.drift_service import DriftService
from app.services.snapshot_service import SnapshotService


class FakeAuditRunRepo:
    def __init__(self):
        self.runs = {}

    def get_run(self, run_id: int):
        summary = self.runs.get(run_id)
        if not summary:
            return None
        from app.domain.entities.audit_run import AuditRunDetail
        return AuditRunDetail(summary=summary, findings=())


def test_baseline_service_approval_and_pinning(tmp_path: Path):
    db_file = tmp_path / "test_baseline_svc.db"
    init_db(db_file)
    snap_dir = tmp_path / "snapshots"

    # Insert device and audit runs into DB for foreign key satisfaction
    import sqlite3
    conn = sqlite3.connect(db_file)
    with conn:
        conn.execute(
            """
            INSERT INTO devices (device_id, name, host, port, platform, created_at, updated_at)
            VALUES ('dev1', 'D1', '10.0.0.1', 22, 'cisco_ios', '2026-01-01', '2026-01-01')
            """
        )
        for r_id in range(100, 106):
            conn.execute(
                """
                INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at)
                VALUES (?, 'dev1', 'cisco_ios', 'COMPLETED', '2026-01-01', '2026-01-01')
                """,
                (r_id,),
            )
    conn.close()

    file_store = FileSnapshotStore(snap_dir)
    snap_repo = SqliteSnapshotRepository(db_file)
    base_repo = SqliteBaselineRepository(db_file)
    drift_repo = SqliteDriftRepository(db_file)

    snap_svc = SnapshotService(
        snapshot_repository=snap_repo,
        file_store=file_store,
        redactor=ConfigRedactor(hmac_key="secret"),
        baseline_repository=base_repo,
        keep=2,
    )

    audit_repo = FakeAuditRunRepo()
    drift_svc = DriftService()

    base_svc = BaselineService(
        baseline_repository=base_repo,
        drift_repository=drift_repo,
        snapshot_service=snap_svc,
        drift_service=drift_svc,
        audit_run_repository=audit_repo,
    )

    # 1. Setup audit run and snapshot
    audit_repo.runs[100] = AuditRunSummary(
        id=100,
        device_id="dev1",
        platform="cisco_ios",
        status=AuditStatus.COMPLETED,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        hostname=None,
        error_code=None,
        error_message=None,
        pass_count=5,
        fail_count=2,
        unknown_count=0,
    )

    snap1 = snap_svc.create_for_run("dev1", 100, "hostname R1\n")
    assert snap1 is not None

    # 2. Approve without confirm when fail_count > 0 -> 409 error
    with pytest.raises(BaselineFailuresNotConfirmedError) as exc_info:
        base_svc.approve(
            device_id="dev1",
            snapshot_id=snap1.id,
            approved_by="admin",
            confirm_with_failures=False,
        )
    assert exc_info.value.fail_count == 2

    # 3. Approve with confirm -> success
    b1 = base_svc.approve(
        device_id="dev1",
        snapshot_id=snap1.id,
        approved_by="admin",
        note="Approved with 2 failures",
        confirm_with_failures=True,
    )
    assert b1.status == BaselineStatus.ACTIVE
    assert b1.fail_count_at_approval == 2

    # 4. Snapshot in use cannot be deleted
    with pytest.raises(SnapshotInUseError):
        snap_svc.delete(snap1.id)

    # 5. Retention policy: create snapshots beyond keep limit (keep=2)
    # The active baseline snapshot snap1 must not be deleted and not count towards keep
    for run_id in range(101, 105):
        audit_repo.runs[run_id] = AuditRunSummary(
            id=run_id,
            device_id="dev1",
            platform="cisco_ios",
            status=AuditStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            hostname=None,
            error_code=None,
            error_message=None,
            pass_count=5,
            fail_count=0,
            unknown_count=0,
        )
        snap_svc.create_for_run("dev1", run_id, f"hostname R1\n! run {run_id}\n")

    # Verify snap1 is still intact
    snap1_check = snap_svc.get_metadata(snap1.id)
    assert snap1_check.id == snap1.id

    # 6. Retire baseline -> snapshot is no longer pinned and can be deleted
    base_svc.retire("dev1", "admin")
    assert base_repo.is_snapshot_pinned(snap1.id) is False
    snap_svc.delete(snap1.id)
