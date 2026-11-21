"""API and unit tests for AI explanation endpoints (Spec 7, 8.8, 10.10, 10.11)."""

from __future__ import annotations

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.connectors.fake_connector import FakeConnector
from app.core.config import Settings
from app.domain.entities.user import Role
from app.domain.interfaces.llm_client import LLMClient
from app.factories.connector_factory import ConnectorFactory
from app.main import create_app
from app.repositories.database import init_db
from app.repositories.sqlite_user_repository import SQLiteUserRepository
from app.security.password_hasher import Argon2PasswordHasher


class FakeLLMClient(LLMClient):
    def __init__(self, model_name: str = "mock-ollama"):
        self._model = model_name
        self.call_count = 0

    @property
    def model(self) -> str:
        return self._model

    def is_reachable(self) -> bool:
        return True

    def generate_json(self, *, system: str, user: str, schema: dict[str, object], timeout_seconds: int) -> dict[str, object]:
        self.call_count += 1
        return {
            "summary": "Phân tích an ninh: Thiết bị còn một số thiếu sót cần khắc phục.",
            "priorities": [{"rule_id": "NET-001", "reason": "Cần ưu tiên hàng đầu"}],
            "risks": [{"rule_id": "NET-001", "warning": "Nguy cơ lộ thông tin nếu không sửa"}],
        }


class TestAiApi:
    @pytest.fixture
    def fake_llm(self):
        return FakeLLMClient()

    @pytest.fixture
    def test_app(self, tmp_path: Path, fake_llm):
        db_file = tmp_path / "ai_api.db"
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
            ai_enabled=True,
        )

        class FakeConnFactory(ConnectorFactory):
            def create(self, target, credentials):
                return FakeConnector(config_text="hostname Router-AI-01\ninterface GigabitEthernet0/0\n")

        app = create_app(settings=settings, connector_factory=FakeConnFactory())
        # Replace LLM client with test fake
        app.state.ai_explain_service.llm_client = fake_llm
        return app

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

    def test_ai_status_and_explain_flow(self, test_app, fake_llm):
        headers = {"Host": "testserver", "Origin": "http://testserver"}
        admin_c = TestClient(test_app, headers=headers)
        op_c = TestClient(test_app, headers=headers)
        view_c = TestClient(test_app, headers=headers)

        self._login(admin_c, "admin_user")
        self._login(op_c, "operator_user")
        self._login(view_c, "viewer_user")

        # 1. GET /ai/status (viewer, operator, admin)
        res_status = view_c.get("/api/v1/ai/status")
        assert res_status.status_code == 200
        assert res_status.json()["enabled"] is True
        assert res_status.json()["reachable"] is True

        # 2. Create device & audit
        dev_id = "Router-AI-01"
        payload = {
            "device_id": dev_id,
            "name": "Lab AI Router",
            "host": "192.168.1.60",
            "port": 22,
            "platform": "cisco_ios",
        }
        resp = admin_c.post("/api/v1/devices", json=payload)
        assert resp.status_code == 201

        creds = {"credentials": {"username": "admin", "password": "Password123!"}}
        audit_resp = admin_c.post(f"/api/v1/devices/{dev_id}/audit", json=creds)
        assert audit_resp.status_code == 201
        run_id = audit_resp.json()["summary"]["id"]

        # 3. Viewer cannot POST explain (operator+ only)
        resp_view_explain = view_c.post(f"/api/v1/audits/{run_id}/explain")
        assert resp_view_explain.status_code == 403

        # 4. Operator generates explanation
        resp_op_explain = op_c.post(f"/api/v1/audits/{run_id}/explain")
        assert resp_op_explain.status_code == 200
        data = resp_op_explain.json()
        assert data["run_id"] == run_id
        assert data["generated_by_ai"] is True
        assert "Phân tích an ninh" in data["summary"]
        assert fake_llm.call_count == 1

        # 5. Subsequent call returns cached version without calling LLM again
        resp_cached = op_c.post(f"/api/v1/audits/{run_id}/explain")
        assert resp_cached.status_code == 200
        assert fake_llm.call_count == 1

        # 6. Force re-generation calls LLM again
        resp_forced = op_c.post(f"/api/v1/audits/{run_id}/explain?force=1")
        assert resp_forced.status_code == 200
        assert fake_llm.call_count == 2

        # 7. Viewer can GET explanation
        resp_view_get = view_c.get(f"/api/v1/audits/{run_id}/explanation")
        assert resp_view_get.status_code == 200
        assert resp_view_get.json()["summary"] == data["summary"]
