"""Tests for audit API endpoints (Spec 8.9)."""

from __future__ import annotations

import threading
from typing import Any
import pytest
from starlette.testclient import TestClient

from app.connectors.fake_connector import FakeConnector
from app.domain.errors import ConnectionTimeoutError


@pytest.fixture(autouse=True)
def seed_device(auth_client: TestClient):
    payload = {
        "device_id": "R1",
        "name": "Router 1",
        "host": "192.168.1.1",
        "port": 22,
        "platform": "cisco_ios",
    }
    resp = auth_client.post("/api/v1/devices", json=payload)
    assert resp.status_code == 201


def test_audit_with_body_credentials(auth_client: TestClient):
    payload = {
        "credentials": {
            "username": "custom_user",
            "password": "CustomPassword123!",
            "enable_secret": "CustomEnable123!",
        }
    }
    resp = auth_client.post("/api/v1/devices/R1/audit", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["summary"]["status"] == "COMPLETED"
    assert data["summary"]["device_id"] == "R1"
    assert len(data["findings"]) == 8


def test_audit_with_fallback_environment_credentials(auth_client: TestClient):
    # Empty body uses default_credentials from environment
    resp = auth_client.post("/api/v1/devices/R1/audit", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["summary"]["status"] == "COMPLETED"


def test_audit_connection_failure_returns_201_with_failed_status(
    auth_client: TestClient, connector_holder: dict[str, FakeConnector]
):
    # Set connector for R1 to fail on connection
    fail_conn = FakeConnector(config_text="hostname R1\n", fail_on=ConnectionTimeoutError)
    connector_holder["R1"] = fail_conn

    resp = auth_client.post("/api/v1/devices/R1/audit", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["summary"]["status"] == "FAILED"
    assert data["summary"]["error_code"] == "CONNECT_TIMEOUT"
    assert len(data["findings"]) == 0


def test_audit_nonexistent_device_returns_404(auth_client: TestClient):
    resp = auth_client.post("/api/v1/devices/NONEXISTENT/audit", json={})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DEVICE_NOT_FOUND"


def test_get_nonexistent_audit_returns_404(auth_client: TestClient):
    resp = auth_client.get("/api/v1/audits/99999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "AUDIT_NOT_FOUND"

    resp_findings = auth_client.get("/api/v1/audits/99999/findings")
    assert resp_findings.status_code == 404
    assert resp_findings.json()["error"]["code"] == "AUDIT_NOT_FOUND"


def test_concurrent_audit_returns_409(
    auth_client: TestClient, connector_holder: dict[str, FakeConnector]
):
    block_event = threading.Event()
    ready_event = threading.Event()

    class BlockingConn(FakeConnector):
        def get_running_config(self) -> str:
            ready_event.set()
            block_event.wait(timeout=5.0)
            return super().get_running_config()

    blocking_conn = BlockingConn(config_text="hostname R1\n", hostname="R1")
    connector_holder["R1"] = blocking_conn

    thread_status: list[int] = []

    def run_first():
        resp = auth_client.post("/api/v1/devices/R1/audit", json={})
        thread_status.append(resp.status_code)

    t = threading.Thread(target=run_first)
    t.start()

    assert ready_event.wait(timeout=2.0)

    try:
        # Concurrent second request on same device must return 409
        second_resp = auth_client.post("/api/v1/devices/R1/audit", json={})
        assert second_resp.status_code == 409
        assert second_resp.json()["error"]["code"] == "AUDIT_ALREADY_RUNNING"
    finally:
        block_event.set()
        t.join(timeout=2.0)

    assert thread_status == [201]


def test_list_audits_pagination(auth_client: TestClient):
    # Run 3 audits
    for _ in range(3):
        auth_client.post("/api/v1/devices/R1/audit", json={})

    resp = auth_client.get("/api/v1/devices/R1/audits?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    resp_page2 = auth_client.get("/api/v1/devices/R1/audits?limit=2&offset=2")
    assert resp_page2.status_code == 200
    data2 = resp_page2.json()
    assert len(data2["items"]) == 1


def test_filter_findings_by_status_and_severity(auth_client: TestClient):
    # Insecure config produces 8 FAIL findings
    audit_resp = auth_client.post("/api/v1/devices/R1/audit", json={})
    run_id = audit_resp.json()["summary"]["id"]

    # All findings
    all_resp = auth_client.get(f"/api/v1/audits/{run_id}/findings")
    assert all_resp.status_code == 200
    assert len(all_resp.json()) == 8

    # Filter status=FAIL
    fail_resp = auth_client.get(f"/api/v1/audits/{run_id}/findings?status=FAIL")
    assert fail_resp.status_code == 200
    assert len(fail_resp.json()) == 8

    # Filter status=PASS (should be 0 for insecure config)
    pass_resp = auth_client.get(f"/api/v1/audits/{run_id}/findings?status=PASS")
    assert pass_resp.status_code == 200
    assert len(pass_resp.json()) == 0

    # Filter invalid status returns 422
    invalid_status = auth_client.get(f"/api/v1/audits/{run_id}/findings?status=INVALID_STATUS")
    assert invalid_status.status_code == 422

    # Filter invalid severity returns 422
    invalid_sev = auth_client.get(f"/api/v1/audits/{run_id}/findings?severity=SUPER_HIGH")
    assert invalid_sev.status_code == 422
