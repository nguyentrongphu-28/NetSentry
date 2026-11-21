"""API and RBAC tests for audit compare / findings diff endpoints (Spec 7, 10.11)."""

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


class TestCompareApi:
    @pytest.fixture
    def test_app(self, tmp_path: Path):
        db_file = tmp_path / "comp_api.db"
        snap_dir = tmp_path / "snapshots"
        init_db(db_file)

        user_repo = SQLiteUserRepository(db_file)
        hasher = Argon2PasswordHasher()

        user_repo.add("admin_user", hasher.hash("AdminPassword123!"), Role.ADMIN, must_change_password=False)
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
                return FakeConnector(config_text="hostname Router-Compare-01\ninterface GigabitEthernet0/0\n")

        return create_app(settings=settings, connector_factory=FakeConnFactory())

    def _login(self, client: TestClient, username: str) -> None:
        pwd_map = {
            "admin_user": "AdminPassword123!",
            "viewer_user": "ViewerPassword123!",
        }
        res = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": pwd_map[username]},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert res.status_code == 200

    def test_compare_audit_runs(self, test_app):
        headers = {"Host": "testserver", "Origin": "http://testserver"}
        admin_c = TestClient(test_app, headers=headers)
        view_c = TestClient(test_app, headers=headers)

        self._login(admin_c, "admin_user")
        self._login(view_c, "viewer_user")

        compare_device = "Router-Compare-01"
        payload = {
            "device_id": compare_device,
            "name": "Lab Compare Router",
            "host": "192.168.1.51",
            "port": 22,
            "platform": "cisco_ios",
        }
        resp = admin_c.post("/api/v1/devices", json=payload)
        assert resp.status_code == 201

        # First audit
        creds = {"credentials": {"username": "admin", "password": "Password123!"}}
        audit1_resp = admin_c.post(f"/api/v1/devices/{compare_device}/audit", json=creds)
        assert audit1_resp.status_code == 201
        audit1 = audit1_resp.json()
        run1_id = audit1["summary"]["id"]

        # When no prior run exists -> has_previous=False
        comp1 = view_c.get(f"/api/v1/audits/{run1_id}/compare")
        assert comp1.status_code == 200
        data1 = comp1.json()
        assert data1["has_previous"] is False
        assert data1["from_run_id"] is None
        assert data1["to_run_id"] == run1_id

        # Second audit
        audit2_resp = admin_c.post(f"/api/v1/devices/{compare_device}/audit", json=creds)
        assert audit2_resp.status_code == 201
        audit2 = audit2_resp.json()
        run2_id = audit2["summary"]["id"]

        # Compare second with default (first)
        comp2 = view_c.get(f"/api/v1/audits/{run2_id}/compare")
        assert comp2.status_code == 200
        data2 = comp2.json()
        assert data2["has_previous"] is True
        assert data2["from_run_id"] == run1_id
        assert data2["to_run_id"] == run2_id
        assert isinstance(data2["changes"], list)

