"""API and RBAC tests for snapshots and config diff endpoints (Spec 7, 10.11)."""

from __future__ import annotations

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.core.config import Settings
from app.domain.entities.user import Role
from app.main import create_app
from app.repositories.database import init_db
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher
from app.factories.connector_factory import ConnectorFactory
from app.connectors.fake_connector import FakeConnector


class TestSnapshotsApi:
    @pytest.fixture
    def test_app(self, tmp_path: Path):
        db_file = tmp_path / "snap_api.db"
        snap_dir = tmp_path / "snapshots"
        init_db(db_file)

        user_repo = SQLiteUserRepository(db_file)
        hasher = Argon2PasswordHasher()

        user_repo.add("admin_user", hasher.hash("AdminPassword123!"), Role.ADMIN, must_change_password=False)
        user_repo.add("operator_user", hasher.hash("OperatorPassword123!"), Role.OPERATOR, must_change_password=False)
        user_repo.add("viewer_user", hasher.hash("ViewerPassword123!"), Role.VIEWER, must_change_password=False)

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
            snapshot_enabled=True,
            snapshot_content_api=True,
        )

        class FakeConnFactory(ConnectorFactory):
            def create(self, target, credentials):
                return FakeConnector(config_text="hostname Router-Snapshot-01\ninterface GigabitEthernet0/0\n ip address 10.0.0.1 255.255.255.0\n")

        return create_app(settings=settings, connector_factory=FakeConnFactory())

    def _login(self, client: TestClient, username: str) -> None:
        pwd_map = {
            "admin_user": "AdminPassword123!",
            "operator_user": "OperatorPassword123!",
            "viewer_user": "ViewerPassword123!",
        }
        res = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": pwd_map[username]},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert res.status_code == 200

    def test_snapshots_lifecycle_and_rbac(self, test_app):
        headers = {"Host": "testserver", "Origin": "http://testserver"}
        admin_c = TestClient(test_app, headers=headers)
        op_c = TestClient(test_app, headers=headers)
        view_c = TestClient(test_app, headers=headers)

        self._login(admin_c, "admin_user")
        self._login(op_c, "operator_user")
        self._login(view_c, "viewer_user")

        dev_id = "Router-Snapshot-01"
        payload = {
            "device_id": dev_id,
            "name": "Lab Snapshot Router",
            "host": "192.168.1.50",
            "port": 22,
            "platform": "cisco_ios",
        }
        resp = admin_c.post("/api/v1/devices", json=payload)
        assert resp.status_code == 201

        # 1. Trigger audit to generate a snapshot
        creds = {"credentials": {"username": "admin", "password": "Password123!"}}
        audit1_resp = admin_c.post(f"/api/v1/devices/{dev_id}/audit", json=creds)
        assert audit1_resp.status_code == 201
        audit1 = audit1_resp.json()
        run1_id = audit1["summary"]["id"]

        # 2. List snapshots (viewer, operator, admin)
        resp_viewer = view_c.get(f"/api/v1/devices/{dev_id}/snapshots")
        assert resp_viewer.status_code == 200
        snaps = resp_viewer.json()
        assert len(snaps) == 1
        snap1_id = snaps[0]["id"]
        assert snaps[0]["run_id"] == run1_id

        # 3. Viewer cannot get full snapshot content (operator+)
        resp_viewer_detail = view_c.get(f"/api/v1/snapshots/{snap1_id}")
        assert resp_viewer_detail.status_code == 403

        # 4. Operator can get full snapshot content
        resp_op_detail = op_c.get(f"/api/v1/snapshots/{snap1_id}")
        assert resp_op_detail.status_code == 200
        detail = resp_op_detail.json()
        assert "content" in detail
        assert "interface GigabitEthernet0/0" in detail["content"]

        # 5. Trigger second audit
        audit2_resp = admin_c.post(f"/api/v1/devices/{dev_id}/audit", json=creds)
        assert audit2_resp.status_code == 201
        audit2 = audit2_resp.json()
        run2_id = audit2["summary"]["id"]

        # 6. Diff between the two snapshots
        diff_resp = op_c.get(f"/api/v1/devices/{dev_id}/diff?from_run={run1_id}&to_run={run2_id}")
        assert diff_resp.status_code == 200
        diff_data = diff_resp.json()
        assert diff_data["from_run_id"] == run1_id
        assert diff_data["to_run_id"] == run2_id
        assert diff_data["identical"] is True

        # 7. Operator cannot delete snapshot (admin only)
        del_op = op_c.delete(f"/api/v1/snapshots/{snap1_id}")
        assert del_op.status_code == 403

        # 8. Admin deletes snapshot
        del_admin = admin_c.delete(f"/api/v1/snapshots/{snap1_id}")
        assert del_admin.status_code == 204

        # 9. Verify deleted
        get_after_del = op_c.get(f"/api/v1/snapshots/{snap1_id}")
        assert get_after_del.status_code == 404

