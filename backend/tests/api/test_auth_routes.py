"""API tests for authentication endpoints (Section 9.6)."""

from datetime import datetime, timezone
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
def auth_api_client(tmp_path: Path):
    db_file = tmp_path / "auth_api.db"
    init_db(db_file)

    user_repo = SQLiteUserRepository(db_file)
    hasher = Argon2PasswordHasher()

    # Pre-populate test users
    user_repo.add(
        username="admin",
        password_hash=hasher.hash("AdminPassword123!"),
        role=Role.ADMIN,
        must_change_password=False,
    )
    user_repo.add(
        username="newuser",
        password_hash=hasher.hash("InitialPassword123!"),
        role=Role.OPERATOR,
        must_change_password=True,
    )

    settings = Settings(
        db_path=db_file,
        api_key="a" * 32,
        auth_disabled=False,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=True,
        public_mode=False,
        session_cookie_secure=False,  # allow test client over http
    )

    app = create_app(settings=settings)
    return TestClient(app)


class TestAuthRoutes:
    def test_login_success_sets_cookie_and_returns_user(self, auth_api_client: TestClient) -> None:
        resp = auth_api_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "AdminPassword123!"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
        assert data["user"]["must_change_password"] is False

        # Cookie check
        assert "netsentry_session" in resp.cookies
        cookie = resp.cookies["netsentry_session"]
        assert len(cookie) >= 32

    def test_login_invalid_credentials_returns_401(self, auth_api_client: TestClient) -> None:
        resp = auth_api_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "WrongPassword123!"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert resp.json()["error"]["message"] == "Invalid username or password"

    def test_get_me_with_cookie_session(self, auth_api_client: TestClient) -> None:
        # Login first
        auth_api_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "AdminPassword123!"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )

        me_resp = auth_api_client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["user"]["username"] == "admin"
        assert data["capabilities"]["body_credentials"] is True

    def test_logout_revokes_session_and_clears_cookie(self, auth_api_client: TestClient) -> None:
        # Login
        auth_api_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "AdminPassword123!"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )

        # Logout
        logout_resp = auth_api_client.post(
            "/api/v1/auth/logout",
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert logout_resp.status_code == 204

        # Subsequent call with previous session cookie returns 401
        me_resp = auth_api_client.get("/api/v1/auth/me")
        assert me_resp.status_code == 401
        assert me_resp.json()["error"]["code"] == "UNAUTHORIZED"

    def test_must_change_password_blocks_other_endpoints(self, auth_api_client: TestClient) -> None:
        # Login with newuser (must_change_password=True)
        login_resp = auth_api_client.post(
            "/api/v1/auth/login",
            json={"username": "newuser", "password": "InitialPassword123!"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert login_resp.status_code == 200
        assert login_resp.json()["user"]["must_change_password"] is True

        # /auth/me is allowed
        me_resp = auth_api_client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200

        # /devices list is blocked with 403 PASSWORD_CHANGE_REQUIRED
        dev_resp = auth_api_client.get("/api/v1/devices")
        assert dev_resp.status_code == 403
        assert dev_resp.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"

        # Change password
        ch_resp = auth_api_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "InitialPassword123!",
                "new_password": "FreshSecurePassword123!",
            },
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert ch_resp.status_code == 204

        # Now /devices is accessible
        dev_resp2 = auth_api_client.get("/api/v1/devices")
        assert dev_resp2.status_code == 200
