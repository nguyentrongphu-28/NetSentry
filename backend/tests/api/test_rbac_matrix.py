"""API tests for RBAC matrix and exhaustive route security traversal (Section 9.7)."""

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
def rbac_app(tmp_path: Path):
    db_file = tmp_path / "rbac_matrix.db"
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
    )

    return create_app(settings=settings)


class TestRbacMatrix:
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

    def test_unauthenticated_requests_receive_401(self, rbac_app) -> None:
        client = TestClient(rbac_app)

        # /health is public -> 200
        assert client.get("/health").status_code == 200

        # Protected endpoints return 401 when no auth provided
        assert client.get("/api/v1/auth/me").status_code == 401
        assert client.get("/api/v1/devices").status_code == 401
        assert client.post("/api/v1/devices", json={}).status_code == 401
        assert client.get("/api/v1/users").status_code == 401
        assert client.get("/api/v1/security-events").status_code == 401

    def test_exhaustive_app_routes_traversal(self, rbac_app) -> None:
        """Section 5.2 requirement:

        Verify that no route in app.routes (except whitelist) can be accessed
        without authentication.
        """
        client = TestClient(rbac_app)
        whitelist = {"/health", "/api/v1/auth/login"}

        for route in rbac_app.routes:
            path = getattr(route, "path", None)
            if not path or path in whitelist or path.startswith("/static"):
                continue

            methods = getattr(route, "methods", {"GET"})
            for method in methods:
                if method in ("HEAD", "OPTIONS"):
                    continue

                response = client.request(
                    method=method,
                    url=path,
                    headers={"Host": "testserver", "Origin": "http://testserver"},
                )
                assert response.status_code in (401, 404, 405), (
                    f"Route {method} {path} is accessible without authentication! (Got {response.status_code})"
                )

    def test_viewer_permissions(self, rbac_app) -> None:
        client = TestClient(rbac_app)
        self._login(client, "viewer_user")

        # Viewer can read devices and audits
        assert client.get("/api/v1/devices").status_code == 200

        # Viewer CANNOT create devices (403)
        dev_res = client.post(
            "/api/v1/devices",
            json={"device_id": "D1", "name": "D1", "host": "10.0.0.1", "port": 22, "platform": "cisco_ios"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert dev_res.status_code == 403
        assert dev_res.json()["error"]["code"] == "FORBIDDEN"

        # Viewer CANNOT delete devices (403)
        assert client.delete(
            "/api/v1/devices/D1",
            headers={"Host": "testserver", "Origin": "http://testserver"},
        ).status_code == 403

        # Viewer CANNOT manage users or view security events (403)
        assert client.get("/api/v1/users").status_code == 403
        assert client.get("/api/v1/security-events").status_code == 403

    def test_operator_permissions(self, rbac_app) -> None:
        client = TestClient(rbac_app)
        self._login(client, "operator_user")

        # Operator can create device
        create_res = client.post(
            "/api/v1/devices",
            json={"device_id": "R1_OP", "name": "Router 1", "host": "10.0.0.1", "port": 22, "platform": "cisco_ios"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert create_res.status_code == 201

        # Operator CANNOT delete devices (403)
        del_res = client.delete(
            "/api/v1/devices/R1_OP",
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert del_res.status_code == 403

        # Operator CANNOT manage users or view security events (403)
        assert client.get("/api/v1/users").status_code == 403
        assert client.get("/api/v1/security-events").status_code == 403

    def test_admin_permissions(self, rbac_app) -> None:
        client = TestClient(rbac_app)
        self._login(client, "admin_user")

        # Admin can create, read, and delete devices
        create_res = client.post(
            "/api/v1/devices",
            json={"device_id": "R_ADMIN", "name": "Router Admin", "host": "10.0.0.2", "port": 22, "platform": "cisco_ios"},
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert create_res.status_code == 201

        del_res = client.delete(
            "/api/v1/devices/R_ADMIN",
            headers={"Host": "testserver", "Origin": "http://testserver"},
        )
        assert del_res.status_code == 204

        # Admin can view users and security events
        assert client.get("/api/v1/users").status_code == 200
        assert client.get("/api/v1/security-events").status_code == 200
