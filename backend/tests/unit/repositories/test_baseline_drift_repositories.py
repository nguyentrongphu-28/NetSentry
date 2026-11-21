"""Unit tests for SQLite baseline and drift repositories (Spec 9.3)."""

from pathlib import Path
import sqlite3
import pytest

from app.domain.entities.drift import DriftSummary
from app.repositories.database import init_db
from app.repositories.sqlite_baseline_repository import SqliteBaselineRepository
from app.repositories.sqlite_drift_repository import SqliteDriftRepository


def test_baseline_and_drift_repositories_lifecycle(tmp_path: Path):
    db_file = tmp_path / "test_baseline.db"
    init_db(db_file)

    # Insert sample device and audit run
    conn = sqlite3.connect(db_file)
    with conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO devices (device_id, name, host, port, platform, created_at, updated_at)
            VALUES ('dev1', 'Device 1', '10.0.0.1', 22, 'cisco_ios', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at)
            VALUES (101, 'dev1', 'cisco_ios', 'COMPLETED', '2026-01-01T00:00:00Z', '2026-01-01T00:01:00Z')
            """
        )
    conn.close()

    baseline_repo = SqliteBaselineRepository(db_file)
    drift_repo = SqliteDriftRepository(db_file)

    # 1. Set first active baseline
    b1 = baseline_repo.set_active_baseline(
        device_id="dev1",
        snapshot_id=1,
        content_sha256="hash1",
        approved_by="admin",
        note="Initial baseline",
        fail_count_at_approval=0,
    )
    assert b1.id is not None
    assert b1.status.value == "ACTIVE"
    assert baseline_repo.is_snapshot_pinned(1) is True

    # 2. Setting second active baseline retires first
    b2 = baseline_repo.set_active_baseline(
        device_id="dev1",
        snapshot_id=2,
        content_sha256="hash2",
        approved_by="admin",
        note="Second baseline",
        fail_count_at_approval=0,
    )
    assert b2.status.value == "ACTIVE"
    assert baseline_repo.is_snapshot_pinned(1) is False
    assert baseline_repo.is_snapshot_pinned(2) is True

    # Active baseline check
    active = baseline_repo.get_active("dev1")
    assert active is not None
    assert active.id == b2.id

    # History check
    history = baseline_repo.list_history("dev1")
    assert len(history) == 2
    assert history[0].id == b2.id
    assert history[1].id == b1.id
    assert history[1].status.value == "RETIRED"

    # 3. Drift summary save and retrieve
    summary = DriftSummary(
        status="DRIFTED",
        added_blocks=1,
        removed_blocks=0,
        changed_blocks=1,
        security_relevant_count=1,
    )
    drift_repo.save_summary(
        run_id=101,
        device_id="dev1",
        baseline_id=b2.id,
        checked_at="2026-01-01T00:01:00Z",
        summary=summary,
    )

    by_run = drift_repo.get_by_run(101)
    assert by_run is not None
    assert by_run[0] == b2.id
    assert by_run[1].status == "DRIFTED"

    drift_hist = drift_repo.list_history("dev1")
    assert len(drift_hist) == 1
    assert drift_hist[0]["run_id"] == 101

    # 4. Cascade delete device
    conn = sqlite3.connect(db_file)
    with conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM devices WHERE device_id = 'dev1'")
    conn.close()

    assert baseline_repo.get_active("dev1") is None
    assert len(baseline_repo.list_history("dev1")) == 0
    assert drift_repo.get_by_run(101) is None
