"""Tests for API authentication and authorization (Spec 8.7)."""

from __future__ import annotations

from pathlib import Path
from starlette.testclient import TestClient

from app.core.config import Settings
from app.factories.connector_factory import ConnectorFactory
from app.main import create_app
from tests.api.conftest import TEST_API_KEY


def test_health_check_requires_no_auth(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_protected_routes_without_key_return_401(client: TestClient):
    endpoints = [
        ("GET", "/api/v1/devices"),
        ("POST", "/api/v1/devices"),
        ("GET", "/api/v1/devices/R1"),
        ("DELETE", "/api/v1/devices/R1"),
        ("POST", "/api/v1/devices/R1/audit"),
        ("GET", "/api/v1/devices/R1/audits"),
        ("GET", "/api/v1/audits/1"),
        ("GET", "/api/v1/audits/1/findings"),
    ]

    for method, path in endpoints:
        resp = client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} expected 401, got {resp.status_code}"
        data = resp.json()
        assert data == {
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Invalid or missing API key",
            }
        }


def test_protected_routes_with_invalid_key_return_401(client: TestClient):
    headers = {"X-API-Key": "completely-invalid-key-12345"}
    resp = client.get("/api/v1/devices", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_protected_routes_with_valid_key_return_200(auth_client: TestClient):
    resp = auth_client.get("/api/v1/devices")
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_auth_disabled_allows_requests_without_key(
    tmp_path: Path, fake_connector_factory: ConnectorFactory
):
    disabled_settings = Settings(
        db_path=tmp_path / "disabled_auth.db",
        api_key=None,
        auth_disabled=True,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=True,
    )
    app = create_app(disabled_settings, connector_factory=fake_connector_factory)
    unauthenticated_client = TestClient(app)

    resp = unauthenticated_client.get("/api/v1/devices")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}
