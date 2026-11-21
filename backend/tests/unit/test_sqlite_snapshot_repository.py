from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest
import sqlite3

from app.domain.entities.ai_explanation import AiExplanation, PriorityItem, RiskNote
from app.domain.entities.snapshot import ConfigSnapshot
from app.repositories.database import init_db, connect
from app.repositories.sqlite_ai_explanation_repository import SqliteAiExplanationRepository
from app.repositories.sqlite_snapshot_repository import SqliteSnapshotRepository


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    db_file = tmp_path / "test_snapshot.db"
    init_db(db_file)
    conn = connect(db_file)
    # Seed a device and an audit run
    with conn:
        conn.execute(
            """
            INSERT INTO devices (device_id, name, host, port, platform, created_at, updated_at)
            VALUES ('dev-1', 'Router 1', '10.0.0.1', 22, 'cisco_ios', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at)
            VALUES (1, 'dev-1', 'cisco_ios', 'COMPLETED', '2026-01-01T00:00:00Z', '2026-01-01T00:01:00Z'),
                   (2, 'dev-1', 'cisco_ios', 'COMPLETED', '2026-01-02T00:00:00Z', '2026-01-02T00:01:00Z'),
                   (3, 'dev-1', 'cisco_ios', 'COMPLETED', '2026-01-03T00:00:00Z', '2026-01-03T00:01:00Z')
            """
        )
    return conn


def test_snapshot_repository_crud_and_retention(db_conn: sqlite3.Connection):
    repo = SqliteSnapshotRepository(db_conn)

    s1 = ConfigSnapshot(
        id=0,
        device_id="dev-1",
        run_id=1,
        created_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        content_sha256="hash1",
        size_bytes=100,
        line_count=10,
        redaction_version=1,
    )
    s2 = ConfigSnapshot(
        id=0,
        device_id="dev-1",
        run_id=2,
        created_at=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        content_sha256="hash2",
        size_bytes=200,
        line_count=20,
        redaction_version=1,
    )
    s3 = ConfigSnapshot(
        id=0,
        device_id="dev-1",
        run_id=3,
        created_at=datetime(2026, 1, 3, 0, 0, tzinfo=timezone.utc),
        content_sha256="hash3",
        size_bytes=300,
        line_count=30,
        redaction_version=1,
    )

    saved1 = repo.save(s1, "dev-1/1.cfg")
    saved2 = repo.save(s2, "dev-1/2.cfg")
    saved3 = repo.save(s3, "dev-1/3.cfg")

    assert saved1.id > 0
    assert saved2.id > saved1.id

    # List ordered by created_at DESC
    snapshots = repo.list_for_device("dev-1", limit=10)
    assert len(snapshots) == 3
    assert [s.run_id for s in snapshots] == [3, 2, 1]

    # Test UNIQUE(run_id)
    with pytest.raises(sqlite3.IntegrityError):
        repo.save(s1, "dev-1/dup.cfg")

    # Enforce retention: keep 2 -> deletes run_id 1
    deleted_files = repo.enforce_retention("dev-1", keep=2)
    assert deleted_files == ["dev-1/1.cfg"]
    remaining = repo.list_for_device("dev-1")
    assert len(remaining) == 2
    assert [s.run_id for s in remaining] == [3, 2]


def test_snapshot_cascade_delete(db_conn: sqlite3.Connection):
    repo = SqliteSnapshotRepository(db_conn)
    s = ConfigSnapshot(
        id=0,
        device_id="dev-1",
        run_id=1,
        created_at=datetime.now(timezone.utc),
        content_sha256="hash1",
        size_bytes=100,
        line_count=10,
        redaction_version=1,
    )
    repo.save(s, "dev-1/1.cfg")

    # Delete device -> cascade to snapshots
    with db_conn:
        db_conn.execute("DELETE FROM devices WHERE device_id = 'dev-1'")

    assert repo.get_by_run_id(1) is None
    assert len(repo.list_for_device("dev-1")) == 0


def test_ai_explanation_repository_crud_and_cascade(db_conn: sqlite3.Connection):
    repo = SqliteAiExplanationRepository(db_conn)

    expl = AiExplanation(
        run_id=2,
        created_at=datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc),
        model="qwen2.5:7b-instruct",
        prompt_version=1,
        input_sha256="input_hash_123",
        summary="Cấu hình an ninh mức trung bình.",
        priorities=(PriorityItem(rule_id="NET-001", reason="Nghiêm trọng"),),
        risks=(RiskNote(rule_id="NET-001", warning="Mất kết nối SSH"),),
        generated_by_ai=True,
    )

    repo.save(expl)

    fetched = repo.get(2)
    assert fetched is not None
    assert fetched.run_id == 2
    assert fetched.model == "qwen2.5:7b-instruct"
    assert fetched.summary == "Cấu hình an ninh mức trung bình."
    assert len(fetched.priorities) == 1
    assert fetched.priorities[0].rule_id == "NET-001"
    assert len(fetched.risks) == 1

    # Cascade on audit_run delete
    with db_conn:
        db_conn.execute("DELETE FROM audit_runs WHERE id = 2")

    assert repo.get(2) is None
