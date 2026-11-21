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

CREATE TABLE IF NOT EXISTS config_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id         TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    run_id            INTEGER NOT NULL UNIQUE REFERENCES audit_runs(id) ON DELETE CASCADE,
    created_at        TEXT NOT NULL,
    content_sha256    TEXT NOT NULL,
    size_bytes        INTEGER NOT NULL,
    line_count        INTEGER NOT NULL,
    redaction_version INTEGER NOT NULL,
    file_name         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_device ON config_snapshots(device_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ai_explanations (
    run_id          INTEGER PRIMARY KEY REFERENCES audit_runs(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL,
    model           TEXT NOT NULL,
    prompt_version  INTEGER NOT NULL,
    input_sha256    TEXT NOT NULL,
    content_json    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baselines (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id              TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    snapshot_id            INTEGER NOT NULL,
    content_sha256         TEXT NOT NULL,
    status                 TEXT NOT NULL CHECK (status IN ('ACTIVE','RETIRED')),
    approved_by            TEXT NOT NULL,
    approved_at            TEXT NOT NULL,
    note                   TEXT,
    fail_count_at_approval INTEGER NOT NULL,
    retired_at             TEXT,
    retired_by             TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_baseline_active
    ON baselines(device_id) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_baseline_device
    ON baselines(device_id, approved_at DESC);

CREATE TABLE IF NOT EXISTS drift_results (
    run_id                  INTEGER PRIMARY KEY REFERENCES audit_runs(id) ON DELETE CASCADE,
    device_id               TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    baseline_id             INTEGER NOT NULL,
    checked_at              TEXT NOT NULL,
    status                  TEXT NOT NULL CHECK (status IN ('IN_SYNC','DRIFTED')),
    added_blocks            INTEGER NOT NULL,
    removed_blocks          INTEGER NOT NULL,
    changed_blocks          INTEGER NOT NULL,
    security_relevant_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_drift_device
    ON drift_results(device_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS remediation_plans (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id            TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    run_id               INTEGER NOT NULL,
    rule_id              TEXT NOT NULL,
    template_id          TEXT NOT NULL,
    template_version     INTEGER NOT NULL,
    risk_level           TEXT NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
    commands_json        TEXT NOT NULL,
    persist_after_verify INTEGER NOT NULL DEFAULT 0,
    plan_hash            TEXT NOT NULL,
    status               TEXT NOT NULL CHECK (status IN (
        'PROPOSED','APPROVED','REJECTED','CANCELLED','EXPIRED',
        'APPLYING','APPLIED','VERIFIED','VERIFY_FAILED','FAILED','ROLLED_BACK')),
    proposed_by          TEXT NOT NULL,
    proposed_at          TEXT NOT NULL,
    decided_by           TEXT,
    decided_at           TEXT,
    decision_reason      TEXT,
    approved_plan_hash   TEXT,
    expires_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_plan_active
    ON remediation_plans(device_id, rule_id)
    WHERE status IN ('PROPOSED','APPROVED','APPLYING');
CREATE INDEX IF NOT EXISTS idx_plan_device
    ON remediation_plans(device_id, proposed_at DESC);

CREATE TABLE IF NOT EXISTS remediation_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id     INTEGER NOT NULL REFERENCES remediation_plans(id) ON DELETE CASCADE,
    occurred_at TEXT NOT NULL,
    actor       TEXT,
    event_type  TEXT NOT NULL,
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_plan_events
    ON remediation_events(plan_id, id);

CREATE TABLE IF NOT EXISTS remediation_executions (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id                INTEGER NOT NULL REFERENCES remediation_plans(id) ON DELETE CASCADE,
    mode                   TEXT NOT NULL CHECK (mode IN ('dry_run','live')),
    started_at             TEXT NOT NULL,
    finished_at            TEXT,
    started_by             TEXT NOT NULL,
    result                 TEXT NOT NULL CHECK (result IN
          ('RUNNING','DRY_RUN_OK','VERIFIED','VERIFY_FAILED','ROLLED_BACK','FAILED')),
    failure_code           TEXT,
    changes_sent           INTEGER NOT NULL DEFAULT 0,
    pre_run_id             INTEGER,
    post_run_id            INTEGER,
    rollback_run_id        INTEGER,
    persist_status         TEXT NOT NULL DEFAULT 'NOT_REQUESTED'
          CHECK (persist_status IN ('NOT_REQUESTED','SAVED','FAILED')),
    needs_manual_attention INTEGER NOT NULL DEFAULT 0,
    steps_json             TEXT NOT NULL DEFAULT '[]',
    acknowledged_at        TEXT,
    acknowledged_by        TEXT,
    acknowledgement_note   TEXT
);
CREATE INDEX IF NOT EXISTS idx_exec_plan ON remediation_executions(plan_id, id);
CREATE INDEX IF NOT EXISTS idx_exec_attention ON remediation_executions(needs_manual_attention) WHERE needs_manual_attention = 1;
"""

_SCHEMA_VERSION = 6


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
