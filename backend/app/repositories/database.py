"""SQLite connection and schema initialisation for NetSentry."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS devices (
    device_id  TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    host       TEXT NOT NULL,
    port       INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    platform   TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (host, port)
);

CREATE TABLE IF NOT EXISTS audit_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id      TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    platform       TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('COMPLETED','FAILED')),
    started_at     TEXT NOT NULL,
    finished_at    TEXT NOT NULL,
    hostname       TEXT,
    error_code     TEXT,
    error_message  TEXT,
    pass_count     INTEGER NOT NULL DEFAULT 0,
    fail_count     INTEGER NOT NULL DEFAULT 0,
    unknown_count  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_audit_runs_device_started
    ON audit_runs(device_id, started_at DESC);

CREATE TABLE IF NOT EXISTS findings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_run_id  INTEGER NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
    rule_id       TEXT NOT NULL,
    title         TEXT NOT NULL,
    severity      TEXT NOT NULL CHECK (severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')),
    status        TEXT NOT NULL CHECK (status IN ('PASS','FAIL','UNKNOWN')),
    evidence_json TEXT NOT NULL,
    rationale     TEXT NOT NULL,
    remediation   TEXT NOT NULL,
    verification  TEXT NOT NULL,
    checked_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(audit_run_id);

CREATE TABLE IF NOT EXISTS users (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    username              TEXT NOT NULL UNIQUE,
    password_hash         TEXT NOT NULL,
    role                  TEXT NOT NULL CHECK (role IN ('admin','operator','viewer')),
    is_active             INTEGER NOT NULL DEFAULT 1,
    must_change_password  INTEGER NOT NULL DEFAULT 1,
    failed_attempts       INTEGER NOT NULL DEFAULT 0,
    locked_until          TEXT,
    created_at            TEXT NOT NULL,
    last_login_at         TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash   TEXT PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    client_ip    TEXT,
    user_agent   TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS security_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at    TEXT NOT NULL,
    event_type     TEXT NOT NULL,
    actor_username TEXT,
    client_ip      TEXT,
    target         TEXT,
    detail         TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_time ON security_events(occurred_at DESC);
"""

_SCHEMA_VERSION = 2


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a new SQLite connection for the given path.

    Creates parent directories if they do not exist.
    Configures row_factory, foreign keys, busy timeout and WAL journal mode.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        # In-memory or temporary DBs may not support WAL; skip silently.
        pass
    return conn


def init_db(db_path: str | Path) -> None:
    """Initialise the database schema idempotently.

    Sets user_version = 2 after creating tables.
    Restricts file permissions to 0o600 on POSIX systems (best-effort).
    Raises RuntimeError if the stored user_version is newer than what this
    code understands (downgrade guard).
    """
    db_file = Path(db_path)
    conn = connect(db_file)
    try:
        row = conn.execute("PRAGMA user_version").fetchone()
        stored_version: int = row[0]

        if stored_version > _SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {stored_version} is newer than "
                f"the application supports ({_SCHEMA_VERSION}). "
                "Please upgrade the application."
            )

        with conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
    finally:
        conn.close()

    # Enforce chmod 0o600 on POSIX for both new and existing DB files (best-effort)
    if os.name == "posix" and db_file.exists() and db_file.is_file():
        try:
            db_file.chmod(0o600)
        except OSError:
            pass
