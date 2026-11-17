"""Tests for device API endpoints (Spec 8.8)."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient


def test_device_crud_lifecycle(auth_client: TestClient):
    # 1. Create device
    payload = {
        "device_id": "Router-Core-01",
        "name": "Datacenter Core Router",
        "host": "192.168.1.1",
        "port": 22,
        "platform": "cisco_ios",
    }
    create_resp = auth_client.post("/api/v1/devices", json=payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["device_id"] == "Router-Core-01"
    assert created_data["name"] == "Datacenter Core Router"
    assert created_data["host"] == "192.168.1.1"
    assert created_data["port"] == 22
    assert created_data["platform"] == "cisco_ios"
    assert "created_at" in created_data
    assert "updated_at" in created_data

    # 2. Get device
    get_resp = auth_client.get("/api/v1/devices/Router-Core-01")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["device_id"] == "Router-Core-01"
    assert get_data["latest_audit"] is None

    # 3. List devices
    list_resp = auth_client.get("/api/v1/devices")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["device_id"] == "Router-Core-01"
    assert items[0]["latest_audit"] is None

    # 4. Trigger audit and verify latest_audit is populated
    audit_resp = auth_client.post("/api/v1/devices/Router-Core-01/audit")
    assert audit_resp.status_code == 201
    audit_data = audit_resp.json()
    run_id = audit_data["summary"]["id"]

    # Verify latest_audit in get and list
    get_with_audit = auth_client.get("/api/v1/devices/Router-Core-01").json()
    assert get_with_audit["latest_audit"] is not None
    assert get_with_audit["latest_audit"]["id"] == run_id

    list_with_audit = auth_client.get("/api/v1/devices").json()["items"]
    assert list_with_audit[0]["latest_audit"] is not None
    assert list_with_audit[0]["latest_audit"]["id"] == run_id

    # 5. Delete device
    del_resp = auth_client.delete("/api/v1/devices/Router-Core-01")
    assert del_resp.status_code == 204

    # 6. Verify 404 after delete
    get_after_del = auth_client.get("/api/v1/devices/Router-Core-01")
    assert get_after_del.status_code == 404
    assert get_after_del.json()["error"]["code"] == "DEVICE_NOT_FOUND"


def test_get_and_delete_nonexistent_device(auth_client: TestClient):
    get_resp = auth_client.get("/api/v1/devices/UNKNOWN")
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "DEVICE_NOT_FOUND"

    del_resp = auth_client.delete("/api/v1/devices/UNKNOWN")
    assert del_resp.status_code == 404
    assert del_resp.json()["error"]["code"] == "DEVICE_NOT_FOUND"


def test_create_duplicate_device_id_returns_409(auth_client: TestClient):
    payload = {"device_id": "R1", "host": "10.0.0.1"}
    auth_client.post("/api/v1/devices", json=payload)

    dup_resp = auth_client.post("/api/v1/devices", json={"device_id": "R1", "host": "10.0.0.2"})
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "DEVICE_EXISTS"


def test_create_duplicate_host_port_returns_409(auth_client: TestClient):
    auth_client.post("/api/v1/devices", json={"device_id": "R1", "host": "10.0.0.1", "port": 22})

    dup_resp = auth_client.post("/api/v1/devices", json={"device_id": "R2", "host": "10.0.0.1", "port": 22})
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "DEVICE_EXISTS"


def test_create_device_extra_fields_forbidden(auth_client: TestClient):
    payload = {
        "device_id": "R1",
        "host": "10.0.0.1",
        "unexpected_field": "hacker_payload",
    }
    resp = auth_client.post("/api/v1/devices", json=payload)
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert any("unexpected_field" in d["field"] or "extra" in d["message"].lower() for d in err.get("details", []))


@pytest.mark.parametrize(
    "bad_id",
    [
        "../etc/passwd",
        "r 1",
        "-r1",
        ".r1",
        "a" * 65,
    ],
)
def test_create_device_invalid_device_id(auth_client: TestClient, bad_id: str):
    resp = auth_client.post("/api/v1/devices", json={"device_id": bad_id, "host": "10.0.0.1"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] in ("VALIDATION_ERROR", "INVALID_DEVICE")


@pytest.mark.parametrize(
    "bad_host",
    [
        "host with space",
        "host/with/slash",
        "user@host",
        "host#anchor",
    ],
)
def test_create_device_invalid_host(auth_client: TestClient, bad_host: str):
    resp = auth_client.post("/api/v1/devices", json={"device_id": "R1", "host": bad_host})
    assert resp.status_code == 422


@pytest.mark.parametrize("bad_port", [0, -1, 65536, 100000])
def test_create_device_invalid_port(auth_client: TestClient, bad_port: int):
    resp = auth_client.post("/api/v1/devices", json={"device_id": "R1", "host": "10.0.0.1", "port": bad_port})
    assert resp.status_code == 422
