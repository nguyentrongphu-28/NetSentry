"""API tests for security audit logging and user admin endpoints (Section 9.10)."""

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
def admin_api_client(tmp_path: Path):
    db_file = tmp_path / "admin_api.db"
    init_db(db_file)

    user_repo = SQLiteUserRepository(db_file)
    hasher = Argon2PasswordHasher()

    user_repo.add("admin", hasher.hash("AdminPassword123!"), Role.ADMIN, must_change_password=False)

    settings = Settings(
        db_path=db_file,
        api_key="a" * 32,
        auth_disabled=False,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=False,
        public_mode=False,
        session_cookie_secure=False,
    )

    app = create_app(settings=settings)
    client = TestClient(app)

    # Login as admin
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "AdminPassword123!"},
        headers={"Host": "testserver", "Origin": "http://testserver"},
    )
    return client


class TestUsersAndEventsApi:
    def test_user_management_lifecycle(self, admin_api_client: TestClient) -> None:
        # 1. Create User
        create_res = admin_api_client.post(
            "/api/v1/users",
            json={"username": "testoperator", "password": "InitialPassword123!", "role": "operator"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert create_res.status_code == 201
        user_id = create_res.json()["id"]
        assert create_res.json()["username"] == "testoperator"
        assert create_res.json()["role"] == "operator"
        assert create_res.json()["must_change_password"] is True

        # 2. Update role and active
        patch_res = admin_api_client.patch(
            f"/api/v1/users/{user_id}",
            json={"role": "viewer", "is_active": False},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["role"] == "viewer"
        assert patch_res.json()["is_active"] is False

        # 3. Reset Password
        reset_res = admin_api_client.post(
            f"/api/v1/users/{user_id}/reset-password",
            json={"new_password": "NewResetPassword123!"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert reset_res.status_code == 204

        # 4. Check security events captured these actions
        events_res = admin_api_client.get("/api/v1/security-events")
        assert events_res.status_code == 200
        events = events_res.json()
        event_types = [e["event_type"] for e in events]
        assert "USER_CREATED" in event_types
        assert "USER_UPDATED" in event_types
        assert "PASSWORD_RESET" in event_types

        # Verify no passwords in event details
        for ev in events:
            assert "InitialPassword" not in str(ev["detail"])
            assert "NewResetPassword" not in str(ev["detail"])
