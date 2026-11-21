"""Unit tests for database initialisation and connection handling (Spec 8.1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest

from app.repositories.database import _SCHEMA_VERSION, connect, init_db


def test_init_db_creates_tables_and_sets_user_version(tmp_path: Path):
    db_file = tmp_path / "test.db"
    init_db(db_file)

    conn = connect(db_file)
    try:
        # Check user_version
        row = conn.execute("PRAGMA user_version").fetchone()
        assert row[0] == _SCHEMA_VERSION == 3

        # Check tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [r["name"] for r in tables]
        assert "devices" in table_names
        assert "audit_runs" in table_names
        assert "findings" in table_names
        assert "users" in table_names
        assert "sessions" in table_names
        assert "security_events" in table_names
        assert "config_snapshots" in table_names
        assert "ai_explanations" in table_names

        # Check indexes exist
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = [r["name"] for r in indexes]
        assert "idx_audit_runs_device_started" in index_names
        assert "idx_findings_run" in index_names
        assert "idx_sessions_user" in index_names
        assert "idx_events_time" in index_names
    finally:
        conn.close()


def test_init_db_is_idempotent(tmp_path: Path):
    db_file = tmp_path / "test.db"
    init_db(db_file)
    # Calling init_db again should succeed without error and preserve user_version
    init_db(db_file)

    conn = connect(db_file)
    try:
        row = conn.execute("PRAGMA user_version").fetchone()
        assert row[0] == 3
    finally:
        conn.close()


def test_init_db_downgrade_guard(tmp_path: Path):
    db_file = tmp_path / "test.db"
    conn = connect(db_file)
    try:
        conn.execute("PRAGMA user_version = 99")
    finally:
        conn.close()

    with pytest.raises(RuntimeError, match="newer than the application supports"):
        init_db(db_file)


def test_foreign_keys_are_enabled(tmp_path: Path):
    db_file = tmp_path / "test.db"
    conn = connect(db_file)
    try:
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1
    finally:
        conn.close()


def test_journal_mode_wal_on_disk(tmp_path: Path):
    db_file = tmp_path / "test.db"
    conn = connect(db_file)
    try:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].upper() == "WAL"
    finally:
        conn.close()


def test_connect_creates_parent_directory(tmp_path: Path):
    db_file = tmp_path / "nested" / "dir" / "test.db"
    assert not db_file.parent.exists()
    conn = connect(db_file)
    try:
        assert db_file.parent.exists()
    finally:
        conn.close()
