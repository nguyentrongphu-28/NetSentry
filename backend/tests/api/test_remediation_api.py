"""API and RBAC tests for Remediation endpoints (Spec Section 9.8)."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import pytest
from starlette.testclient import TestClient

from app.core.config import Settings
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.main import create_app
from app.repositories.database import init_db
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher


@pytest.fixture
def remediation_env(tmp_path: Path):
    db_file = tmp_path / "remediation_api.db"
    init_db(db_file)

    user_repo = SQLiteUserRepository(db_file)
    hasher = Argon2PasswordHasher()

    user_repo.add("admin_proposer", hasher.hash("AdminPass123!"), Role.ADMIN, must_change_password=False)
    user_repo.add("admin_approver", hasher.hash("AdminPass456!"), Role.ADMIN, must_change_password=False)
    user_repo.add("operator_user", hasher.hash("OperPass123!"), Role.OPERATOR, must_change_password=False)
    user_repo.add("operator_other", hasher.hash("OperPass456!"), Role.OPERATOR, must_change_password=False)
    user_repo.add("viewer_user", hasher.hash("ViewPass123!"), Role.VIEWER, must_change_password=False)

    now_iso = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_file)
    with conn:
        conn.execute(
            """
            INSERT INTO devices (device_id, name, host, port, platform, created_at, updated_at)
            VALUES ('dev-ios-1', 'Router 1', '10.0.0.1', 22, 'cisco_ios', ?, ?)
            """,
            (now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO audit_runs (id, device_id, platform, status, started_at, finished_at, pass_count, fail_count, unknown_count)
            VALUES (101, 'dev-ios-1', 'cisco_ios', 'COMPLETED', ?, ?, 0, 2, 0)
            """,
            (now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO findings (id, audit_run_id, rule_id, title, severity, status, evidence_json, rationale, remediation, verification, checked_at)
            VALUES (1, 101, 'NET-008', 'HTTP server enabled', 'MEDIUM', 'FAIL', '["ip http server"]', 'rat', 'rem', 'ver', ?)
            """,
            (now_iso,),
        )
        conn.execute(
            """
            INSERT INTO findings (id, audit_run_id, rule_id, title, severity, status, evidence_json, rationale, remediation, verification, checked_at)
            VALUES (2, 101, 'NET-004', 'Password encryption active', 'LOW', 'PASS', '["service password-encryption"]', 'rat', 'rem', 'ver', ?)
            """,
            (now_iso,),
        )
        conn.execute(
            """
            INSERT INTO findings (id, audit_run_id, rule_id, title, severity, status, evidence_json, rationale, remediation, verification, checked_at)
            VALUES (3, 101, 'NET-001', 'Telnet enabled', 'HIGH', 'FAIL', '["transport input telnet"]', 'rat', 'rem', 'ver', ?)
            """,
            (now_iso,),
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
        remediation_enabled=True,
        remediation_require_distinct_approver=True,
    )

    app = create_app(settings=settings)
    client = TestClient(app, headers={"Host": "testserver", "Origin": "http://testserver"})
    return client, app, db_file


def _login(client: TestClient, username: str, password: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200


def test_get_templates(remediation_env):
    client, _, _ = remediation_env

    # 401 unauthenticated
    resp = client.get("/api/v1/remediation/templates")
    assert resp.status_code == 401

    # Viewer can access
    _login(client, "viewer_user", "ViewPass123!")
    resp = client.get("/api/v1/remediation/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    assert "manual_guidance" in data
    assert len(data["templates"]) == 2
    template_rule_ids = {t["rule_id"] for t in data["templates"]}
    assert template_rule_ids == {"NET-008", "NET-004"}
    assert len(data["manual_guidance"]) == 6
    manual_rule_ids = {m["rule_id"] for m in data["manual_guidance"]}
    assert manual_rule_ids == {"NET-001", "NET-002", "NET-003", "NET-005", "NET-006", "NET-007"}


def test_propose_and_approve_flow_rbac(remediation_env):
    client, app, db_file = remediation_env

    # Viewer cannot propose -> 403
    _login(client, "viewer_user", "ViewPass123!")
    resp = client.post(
        "/api/v1/audits/101/findings/NET-008/remediation",
        json={"persist_after_verify": False},
    )
    assert resp.status_code == 403

    # Operator proposes -> 201 Created
    _login(client, "operator_user", "OperPass123!")
    resp = client.post(
        "/api/v1/audits/101/findings/NET-008/remediation",
        json={"persist_after_verify": True},
    )
    assert resp.status_code == 201
    plan_data = resp.json()
    plan_id = plan_data["id"]
    assert plan_data["status"] == "PROPOSED"
    assert plan_data["rule_id"] == "NET-008"
    assert plan_data["persist_after_verify"] is True
    assert "Location" in resp.headers

    # Duplicate propose -> 409 ACTIVE_PLAN_EXISTS
    resp_dup = client.post(
        "/api/v1/audits/101/findings/NET-008/remediation",
        json={"persist_after_verify": False},
    )
    assert resp_dup.status_code == 409
    assert resp_dup.json()["error"]["code"] == "ACTIVE_PLAN_EXISTS"

    # Propose for passing finding -> 422 FINDING_NOT_FAILING
    resp_pass = client.post(
        "/api/v1/audits/101/findings/NET-004/remediation",
        json={"persist_after_verify": False},
    )
    assert resp_pass.status_code == 422
    assert resp_pass.json()["error"]["code"] == "FINDING_NOT_FAILING"

    # Propose for manual rule -> 422 NOT_ELIGIBLE
    resp_inelig = client.post(
        "/api/v1/audits/101/findings/NET-001/remediation",
        json={"persist_after_verify": False},
    )
    assert resp_inelig.status_code == 422
    assert resp_inelig.json()["error"]["code"] == "NOT_ELIGIBLE"

    # GET plan detail as viewer
    _login(client, "viewer_user", "ViewPass123!")
    resp_detail = client.get(f"/api/v1/remediation-plans/{plan_id}")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["commands"] == ["no ip http server"]
    assert detail["approved_hash_matches"] is False
    assert "approved_plan_hash" not in detail
    assert len(detail["timeline"]) == 1

    # Viewer / Operator cannot approve -> 403
    resp_appr_view = client.post(f"/api/v1/remediation-plans/{plan_id}/approve", json={"password": "any"})
    assert resp_appr_view.status_code == 403

    _login(client, "operator_user", "OperPass123!")
    resp_appr_op = client.post(f"/api/v1/remediation-plans/{plan_id}/approve", json={"password": "any"})
    assert resp_appr_op.status_code == 403

    # Admin approver: wrong password -> 422 REAUTH_FAILED
    _login(client, "admin_approver", "AdminPass456!")
    resp_appr_wrong = client.post(f"/api/v1/remediation-plans/{plan_id}/approve", json={"password": "WrongPassword!"})
    assert resp_appr_wrong.status_code == 422
    assert resp_appr_wrong.json()["error"]["code"] == "REAUTH_FAILED"

    # Admin approver: correct password -> 200 APPROVED
    resp_appr_ok = client.post(f"/api/v1/remediation-plans/{plan_id}/approve", json={"password": "AdminPass456!"})
    assert resp_appr_ok.status_code == 200
    appr_detail = resp_appr_ok.json()
    assert appr_detail["status"] == "APPROVED"
    assert appr_detail["decided_by"] == "admin_approver"
    assert appr_detail["approved_hash_matches"] is True
    assert len(appr_detail["timeline"]) == 2


def test_self_approval_blocked(remediation_env):
    client, _, _ = remediation_env

    # Admin proposes
    _login(client, "admin_proposer", "AdminPass123!")
    resp = client.post(
        "/api/v1/audits/101/findings/NET-008/remediation",
        json={"persist_after_verify": False},
    )
    assert resp.status_code == 201
    plan_id = resp.json()["id"]

    # Same admin tries to approve -> 403 SELF_APPROVAL_NOT_ALLOWED
    resp_appr = client.post(f"/api/v1/remediation-plans/{plan_id}/approve", json={"password": "AdminPass123!"})
    assert resp_appr.status_code == 403
    assert resp_appr.json()["error"]["code"] == "SELF_APPROVAL_NOT_ALLOWED"


def test_reject_flow(remediation_env):
    client, _, _ = remediation_env

    _login(client, "operator_user", "OperPass123!")
    resp = client.post(
        "/api/v1/audits/101/findings/NET-008/remediation",
        json={"persist_after_verify": False},
    )
    plan_id = resp.json()["id"]

    # Admin rejects
    _login(client, "admin_approver", "AdminPass456!")
    resp_rej = client.post(
        f"/api/v1/remediation-plans/{plan_id}/reject",
        json={"reason": "Device is in maintenance window next week"},
    )
    assert resp_rej.status_code == 200
    assert resp_rej.json()["status"] == "REJECTED"
    assert resp_rej.json()["decide_reason"] == "Device is in maintenance window next week"


def test_cancel_flow_permissions(remediation_env):
    client, _, _ = remediation_env

    # Operator 1 proposes
    _login(client, "operator_user", "OperPass123!")
    resp = client.post(
        "/api/v1/audits/101/findings/NET-008/remediation",
        json={"persist_after_verify": False},
    )
    plan_id = resp.json()["id"]

    # Operator 2 attempts to cancel -> 403
    _login(client, "operator_other", "OperPass456!")
    resp_cancel_other = client.post(f"/api/v1/remediation-plans/{plan_id}/cancel")
    assert resp_cancel_other.status_code == 403

    # Operator 1 cancels their own plan -> 200
    _login(client, "operator_user", "OperPass123!")
    resp_cancel_own = client.post(f"/api/v1/remediation-plans/{plan_id}/cancel")
    assert resp_cancel_own.status_code == 200
    assert resp_cancel_own.json()["status"] == "CANCELLED"


def test_user_session_required_for_apikey(remediation_env):
    client, _, _ = remediation_env

    # Use API Key instead of session cookie
    resp = client.post(
        "/api/v1/audits/101/findings/NET-008/remediation",
        headers={"X-API-Key": "a" * 32},
        json={"persist_after_verify": False},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "USER_SESSION_REQUIRED"


def test_remediation_disabled(tmp_path: Path):
    db_file = tmp_path / "disabled.db"
    init_db(db_file)
    user_repo = SQLiteUserRepository(db_file)
    hasher = Argon2PasswordHasher()
    user_repo.add("operator_user", hasher.hash("OperPass123!"), Role.OPERATOR, must_change_password=False)

    settings = Settings(
        db_path=db_file,
        api_key="a" * 32,
        auth_disabled=False,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=False,
        public_mode=False,
        session_cookie_secure=False,
        remediation_enabled=False,  # disabled
    )
    app = create_app(settings=settings)
    client = TestClient(app, headers={"Host": "testserver", "Origin": "http://testserver"})
    _login(client, "operator_user", "OperPass123!")

    resp = client.post(
        "/api/v1/audits/101/findings/NET-008/remediation",
        json={"persist_after_verify": False},
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "REMEDIATION_DISABLED"
