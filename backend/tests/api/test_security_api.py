"""Tests for API security, credential masking, CORS, and error redaction (Spec 8.10)."""

from __future__ import annotations

import logging
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.api.schemas.audit import AuditRequest, CredentialsIn
from app.api.schemas.device import DeviceCreate
from app.core.config import Settings
from app.domain.entities.device import Credentials
from app.factories.connector_factory import ConnectorFactory
from app.main import create_app
from tests.api.conftest import FIXTURES_DIR


def test_validation_error_never_leaks_password_or_input_key(auth_client: TestClient):
    fake_password = "SUPER_SECRET_LEAK_TEST_PASSWORD_XYZ"
    bad_payload = {
        "credentials": {
            # missing 'username'
            "password": fake_password,
            "extra_forbidden_key": "injected",
        }
    }

    resp = auth_client.post("/api/v1/devices/R1/audit", json=bad_payload)
    assert resp.status_code == 422

    # Check full response text
    raw_response = resp.text
    assert fake_password not in raw_response, "Password was leaked in 422 response!"

    data = resp.json()
    assert "input" not in data, "FastAPI 'input' key leaked into validation error!"

    # Ensure none of the details contain 'input' or the password
    for detail in data.get("error", {}).get("details", []):
        assert "input" not in detail
        assert fake_password not in str(detail)


def test_credentials_never_stored_in_db_log_or_response(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    fake_connector_factory: ConnectorFactory,
):
    db_file = tmp_path / "security_test.db"
    fake_api_key = "FAKE-API-KEY-0123456789"
    fake_pw = "FAKE-API-PW"
    fake_enable = "FAKE-API-ENABLE"

    settings = Settings(
        db_path=db_file,
        api_key=fake_api_key,
        auth_disabled=False,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=True,
    )
    app = create_app(settings, connector_factory=fake_connector_factory)
    client = TestClient(app, headers={"X-API-Key": fake_api_key})

    # Capture logs at DEBUG level
    caplog.set_level(logging.DEBUG)

    # 1. Create device
    client.post("/api/v1/devices", json={"device_id": "R1", "host": "192.168.1.1"})

    # 2. Run audit with sensitive credentials
    audit_payload = {
        "credentials": {
            "username": "audit_admin",
            "password": fake_pw,
            "enable_secret": fake_enable,
        }
    }
    audit_resp = client.post("/api/v1/devices/R1/audit", json=audit_payload)
    assert audit_resp.status_code == 201

    # 3. Check responses across all endpoints
    endpoints_to_check = [
        audit_resp.text,
        client.get("/api/v1/devices").text,
        client.get("/api/v1/devices/R1").text,
        client.get("/api/v1/devices/R1/audits").text,
        client.get("/api/v1/audits/1").text,
        client.get("/api/v1/audits/1/findings").text,
    ]

    secrets_to_check = [
        fake_api_key,
        fake_pw,
        fake_enable,
        # Fake secrets from ios_insecure.cfg
        "FAKE-ENABLE-PW",
        "FAKE-USER-PW",
        "FAKE-COMMUNITY-RW",
    ]

    for secret in secrets_to_check:
        for text in endpoints_to_check:
            assert secret not in text, f"Secret '{secret}' leaked in HTTP response!"

        # Check logs
        assert secret not in caplog.text, f"Secret '{secret}' leaked in log output!"

    # 4. Check SQLite database files on disk (both main DB and WAL)
    db_bytes = db_file.read_bytes() if db_file.exists() else b""
    wal_file = db_file.with_name(db_file.name + "-wal")
    wal_bytes = wal_file.read_bytes() if wal_file.exists() else b""
    total_db_bytes = db_bytes + wal_bytes

    for secret in secrets_to_check:
        assert secret.encode("utf-8") not in total_db_bytes, f"Secret '{secret}' found in SQLite DB file!"

    # 5. Check repr() of schemas and Settings
    creds_in = CredentialsIn(username="u", password=fake_pw, enable_secret=fake_enable)
    assert fake_pw not in repr(creds_in)
    assert fake_enable not in repr(creds_in)

    audit_req = AuditRequest(credentials=creds_in)
    assert fake_pw not in repr(audit_req)
    assert fake_enable not in repr(audit_req)

    assert fake_api_key not in repr(settings)


def test_internal_server_error_masks_details(
    tmp_path: Path, fake_connector_factory: ConnectorFactory
):
    settings = Settings(
        db_path=tmp_path / "err_test.db",
        api_key="valid-api-key-16-chars",
        auth_disabled=False,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=True,
    )
    app = create_app(settings, connector_factory=fake_connector_factory)
    client = TestClient(
        app,
        headers={"X-API-Key": "valid-api-key-16-chars"},
        raise_server_exceptions=False,
    )

    # Break device_service.list to force 500 error
    def crashing_list():
        raise RuntimeError("Internal DB connection pool exhausted with secret context!")

    app.state.device_service.list = crashing_list

    resp = client.get("/api/v1/devices")
    assert resp.status_code == 500
    data = resp.json()
    assert data == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected internal error occurred",
        }
    }
    assert "secret context" not in resp.text


def test_cors_headers(tmp_path: Path, fake_connector_factory: ConnectorFactory):
    # 1. No CORS origins configured: Access-Control-Allow-Origin should NOT be present
    no_cors_settings = Settings(
        db_path=tmp_path / "no_cors.db",
        api_key="valid-api-key-16-chars",
        auth_disabled=False,
        cors_origins=(),
        allowed_networks=(),
        enable_docs=True,
    )
    app_no_cors = create_app(no_cors_settings, connector_factory=fake_connector_factory)
    client_no_cors = TestClient(app_no_cors)

    resp = client_no_cors.get("/health", headers={"Origin": "https://attacker.com"})
    assert "access-control-allow-origin" not in resp.headers

    # 2. CORS configured: Access-Control-Allow-Origin present for allowed origin
    cors_settings = Settings(
        db_path=tmp_path / "cors.db",
        api_key="valid-api-key-16-chars",
        auth_disabled=False,
        cors_origins=("https://frontend.netsentry.io",),
        allowed_networks=(),
        enable_docs=True,
    )
    app_cors = create_app(cors_settings, connector_factory=fake_connector_factory)
    client_cors = TestClient(app_cors)

    resp_allowed = client_cors.get("/health", headers={"Origin": "https://frontend.netsentry.io"})
    assert resp_allowed.headers.get("access-control-allow-origin") == "https://frontend.netsentry.io"

    # Disallowed origin does not get allow-origin header
    resp_disallowed = client_cors.get("/health", headers={"Origin": "https://unauthorized-origin.com"})
    assert "access-control-allow-origin" not in resp_disallowed.headers
