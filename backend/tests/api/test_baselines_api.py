"""API and RBAC tests for Baseline & Drift endpoints (Spec 9.7 & 9.8)."""

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.core.config import Settings
from app.domain.entities.user import Role
from app.main import create_app
from app.repositories.database import init_db
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher


@pytest.fixture
def baseline_api_env(tmp_path: Path):
    db_file = tmp_path / "baseline_api.db"
    init_db(db_file)
    snap_dir = tmp_path / "snapshots"

    user_repo = SQLiteUserRepository(db_file)
    hasher = Argon2PasswordHasher()

    user_repo.add("admin_user", hasher.hash("AdminPass123!"), Role.ADMIN, must_change_password=False)
    user_repo.add("operator_user", hasher.hash("OperPass123!"), Role.OPERATOR, must_change_password=False)
    user_repo.add("viewer_user", hasher.hash("ViewPass123!"), Role.VIEWER, must_change_password=False)

    # Insert device and audit run
    import sqlite3
    conn = sqlite3.connect(db_file)
    with conn:
        conn.execute(
            """
            INSERT INTO devices (device_id, name, host, port, platform, created_at, updated_at)
            VALUES ('dev1', 'D1', '10.0.0.1', 22, 'cisco_ios', '2026-01-01', '2026-01-01')
            """
        )
        conn.execute(
            """
            INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at, pass_count, fail_count, unknown_count)
            VALUES (100, 'dev1', 'cisco_ios', 'COMPLETED', '2026-01-01', '2026-01-01', 5, 0, 0)
            """
        )
        conn.execute(
            """
            INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at, pass_count, fail_count, unknown_count)
            VALUES (101, 'dev1', 'cisco_ios', 'COMPLETED', '2026-01-02', '2026-01-02', 4, 1, 0)
            """
        )
    conn.close()

    settings = Settings(
        db_path=db_file,
        api_key="a" * 32,
        auth_disabled=False,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=False,
        public_mode=False,
        session_cookie_secure=False,
        snapshot_dir=snap_dir,
    )

    app = create_app(settings=settings)
    client = TestClient(app)

    # Populate snapshot via snapshot_service
    app.state.snapshot_service.create_for_run("dev1", 100, "hostname R1\nip ssh version 2\n")
    app.state.snapshot_service.create_for_run("dev1", 101, "hostname R1\nip ssh version 1\n")

    return client, app


def _login(client: TestClient, username: str, password: str):
    client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Host": "testserver", "Origin": "http://testserver"},
    )


def test_baseline_and_drift_api_rbac_and_flow(baseline_api_env):
    client, app = baseline_api_env

    # 1. Viewer cannot POST baseline (403)
    _login(client, "viewer_user", "ViewPass123!")
    res = client.post(
        "/api/v1/devices/dev1/baseline",
        json={"snapshot_id": 1},
        headers={"Host": "testserver", "Origin": "http://testserver"},
    )
    assert res.status_code == 403

    # 2. Admin can POST baseline
    _login(client, "admin_user", "AdminPass123!")
    res = client.post(
        "/api/v1/devices/dev1/baseline",
        json={"snapshot_id": 1, "note": "Golden Baseline"},
        headers={"Host": "testserver", "Origin": "http://testserver"},
    )
    assert res.status_code == 201
    assert res.json()["status"] == "ACTIVE"
    assert res.json()["note"] == "Golden Baseline"

    # 3. Viewer can GET active baseline and drift summary
    _login(client, "viewer_user", "ViewPass123!")
    res = client.get("/api/v1/devices/dev1/baseline")
    assert res.status_code == 200
    assert res.json()["id"] == 1

    # Viewer GET drift summary
    res = client.get("/api/v1/devices/dev1/drift?run_id=101")
    assert res.status_code == 200
    assert res.json()["summary"]["status"] == "DRIFTED"
    assert res.json()["lines_included"] is False

    # Viewer GET drift with detail=1 -> 403 Forbidden
    res = client.get("/api/v1/devices/dev1/drift?run_id=101&detail=1")
    assert res.status_code == 403

    # 4. Operator can GET drift with detail=1
    _login(client, "operator_user", "OperPass123!")
    res = client.get("/api/v1/devices/dev1/drift?run_id=101&detail=1")
    assert res.status_code == 200
    assert res.json()["lines_included"] is True
    assert len(res.json()["blocks"]) > 0
    assert res.json()["blocks"][0]["key"] == "(global)"

    # 5. Check security events recorded BASELINE_APPROVED and SNAPSHOT_VIEWED
    events = app.state.security_event_service.list_events()
    event_types = [e.event_type.value for e in events]
    assert "BASELINE_APPROVED" in event_types
    assert "SNAPSHOT_VIEWED" in event_types


def test_public_mode_drift_detail_blocked(tmp_path: Path):
    db_file = tmp_path / "pub_baseline_api.db"
    init_db(db_file)
    snap_dir = tmp_path / "snapshots"

    user_repo = SQLiteUserRepository(db_file)
    hasher = Argon2PasswordHasher()
    user_repo.add("admin_user", hasher.hash("AdminPass123!"), Role.ADMIN, must_change_password=False)

    import sqlite3
    conn = sqlite3.connect(db_file)
    with conn:
        conn.execute(
            """
            INSERT INTO devices (device_id, name, host, port, platform, created_at, updated_at)
            VALUES ('dev1', 'D1', '10.0.0.1', 22, 'cisco_ios', '2026-01-01', '2026-01-01')
            """
        )
        conn.execute(
            """
            INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at, pass_count, fail_count, unknown_count)
            VALUES (100, 'dev1', 'cisco_ios', 'COMPLETED', '2026-01-01', '2026-01-01', 5, 0, 0)
            """
        )
    conn.close()

    # Public mode forces snapshot_content_api=False
    settings = Settings(
        db_path=db_file,
        api_key=None,
        auth_disabled=False,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=False,
        session_cookie_secure=False,
        public_mode=True,
        snapshot_dir=snap_dir,
    )
    app = create_app(settings=settings)
    headers = {"Host": "testserver", "Origin": "http://testserver"}
    client = TestClient(app, headers=headers)

    snap = app.state.snapshot_service.create_for_run("dev1", 100, "hostname R1\n")
    app.state.baseline_service.approve(device_id="dev1", snapshot_id=snap.id, approved_by="admin")

    _login(client, "admin_user", "AdminPass123!")

    # Summary works
    res = client.get("/api/v1/devices/dev1/drift?run_id=100")
    assert res.status_code == 200

    # Detail blocked with 403 CONTENT_DISABLED
    res = client.get("/api/v1/devices/dev1/drift?run_id=100&detail=1")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CONTENT_DISABLED"
