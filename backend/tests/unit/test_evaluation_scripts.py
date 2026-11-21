"""Unit tests for performance and remediation evaluation scripts."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import pytest

from evaluation.perf_eval import evaluate_audit_performance, evaluate_offline_engine_throughput
from evaluation.remediation_eval import evaluate_remediation_executions


@pytest.fixture
def mock_perf_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_perf.db"
    conn = sqlite3.connect(db_file)
    with conn:
        conn.execute(
            """
            CREATE TABLE audit_runs (
                id INTEGER PRIMARY KEY,
                device_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                error_code TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE remediation_executions (
                id INTEGER PRIMARY KEY,
                plan_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                started_by TEXT NOT NULL,
                result TEXT NOT NULL,
                failure_code TEXT,
                changes_sent INTEGER NOT NULL,
                persist_status TEXT NOT NULL,
                needs_manual_attention INTEGER NOT NULL
            )
            """
        )

        # Insert sample audit runs
        # 1. 2 seconds duration
        conn.execute(
            "INSERT INTO audit_runs VALUES (1, 'R1', 'cisco_ios', 'COMPLETED', '2026-11-20T10:00:00Z', '2026-11-20T10:00:02Z', NULL)"
        )
        # 2. 4 seconds duration
        conn.execute(
            "INSERT INTO audit_runs VALUES (2, 'R1', 'cisco_ios', 'COMPLETED', '2026-11-20T10:05:00Z', '2026-11-20T10:05:04Z', NULL)"
        )
        # 3. Failed run
        conn.execute(
            "INSERT INTO audit_runs VALUES (3, 'R1', 'cisco_ios', 'FAILED', '2026-11-20T10:10:00Z', '2026-11-20T10:10:01Z', 'CONNECTION_TIMEOUT')"
        )
        # 4. Device R2 completed in 10s
        conn.execute(
            "INSERT INTO audit_runs VALUES (4, 'R2', 'cisco_ios', 'COMPLETED', '2026-11-20T10:15:00Z', '2026-11-20T10:15:10Z', NULL)"
        )

        # Insert sample remediation executions
        # 1. Live VERIFIED, 5s duration
        conn.execute(
            "INSERT INTO remediation_executions VALUES (1, 10, 'live', '2026-11-20T11:00:00Z', '2026-11-20T11:00:05Z', 'admin', 'VERIFIED', NULL, 1, 'SAVED', 0)"
        )
        # 2. Live ROLLED_BACK, 8s duration
        conn.execute(
            "INSERT INTO remediation_executions VALUES (2, 11, 'live', '2026-11-20T11:10:00Z', '2026-11-20T11:10:08Z', 'admin', 'ROLLED_BACK', 'VERIFY_FAILED', 1, 'NOT_REQUESTED', 0)"
        )
        # 3. Dry-run
        conn.execute(
            "INSERT INTO remediation_executions VALUES (3, 12, 'dry_run', '2026-11-20T11:20:00Z', '2026-11-20T11:20:01Z', 'admin', 'VERIFIED', NULL, 0, 'NOT_REQUESTED', 0)"
        )
        # 4. Failed with manual attention
        conn.execute(
            "INSERT INTO remediation_executions VALUES (4, 13, 'live', '2026-11-20T11:30:00Z', '2026-11-20T11:30:03Z', 'admin', 'FAILED', 'WRITE_ERROR', 1, 'NOT_REQUESTED', 1)"
        )

    conn.close()
    return db_file


def test_evaluate_audit_performance(mock_perf_db: Path):
    stats = evaluate_audit_performance(mock_perf_db)
    assert stats["total_runs"] == 4
    assert stats["completed_runs"] == 3
    assert stats["completion_rate"] == "75.0%"
    assert stats["error_distribution"] == {"CONNECTION_TIMEOUT": 1}
    assert stats["durations_seconds"]["min"] == 2.0
    assert stats["durations_seconds"]["max"] == 10.0
    assert "R1" in stats["device_stats"]
    assert "R2" in stats["device_stats"]


def test_evaluate_audit_performance_with_exclusion(mock_perf_db: Path):
    stats = evaluate_audit_performance(mock_perf_db, exclude_devices=("R2",))
    assert stats["total_runs"] == 3
    assert stats["completed_runs"] == 2
    assert "R2" not in stats["device_stats"]


def test_evaluate_remediation_executions(mock_perf_db: Path):
    stats = evaluate_remediation_executions(mock_perf_db)
    assert stats["total_executions"] == 4
    assert stats["live_executions"] == 3
    assert stats["dry_run_executions"] == 1
    assert stats["result_distribution"]["VERIFIED"] == 1
    assert stats["result_distribution"]["ROLLED_BACK"] == 1
    assert stats["result_distribution"]["FAILED"] == 1
    assert stats["needs_manual_attention_count"] == 1
    assert stats["verified_rate"] == "33.3%"
    assert isinstance(stats["verified_wilson_ci_95"], list)
    assert stats["execution_durations_seconds"]["min"] == 3.0
    assert stats["execution_durations_seconds"]["max"] == 8.0


def test_evaluate_offline_engine_throughput():
    corpus_configs = Path(__file__).resolve().parent.parent.parent.parent / "evaluation" / "corpus" / "configs"
    res = evaluate_offline_engine_throughput(corpus_configs, iterations=2)
    assert res["total_evaluations"] > 0
    assert "latency_ms" in res
    assert res["latency_ms"]["median"] >= 0.0
