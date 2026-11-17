"""Unit tests for DeviceService (Spec 8.4)."""

from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
from pathlib import Path
import pytest

from app.domain.errors import DeviceNotFoundError, InvalidDeviceError
from app.repositories.database import init_db
from app.repositories.device_repository import SqliteDeviceRepository
from app.services.device_service import DeviceService


@pytest.fixture
def repo(tmp_path: Path) -> SqliteDeviceRepository:
    p = tmp_path / "test_devices.db"
    init_db(p)
    return SqliteDeviceRepository(p)


@pytest.fixture
def service(repo: SqliteDeviceRepository) -> DeviceService:
    fixed_time = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)
    return DeviceService(repo, clock=lambda: fixed_time)


class TestDeviceValidation:
    def test_valid_device_creation(self, service: DeviceService):
        dev = service.create(
            device_id="Router-01",
            host="192.168.1.1",
            name="Branch Router",
            port=22,
            platform="cisco_ios",
        )
        assert dev.device_id == "Router-01"
        assert dev.name == "Branch Router"
        assert dev.host == "192.168.1.1"
        assert dev.port == 22
        assert dev.platform == "cisco_ios"

    def test_default_name_is_device_id(self, service: DeviceService):
        dev = service.create(device_id="R1", host="10.0.0.1")
        assert dev.name == "R1"

        dev2 = service.create(device_id="R2", host="10.0.0.2", name="   ")
        assert dev2.name == "R2"

    @pytest.mark.parametrize(
        "invalid_id",
        [
            "",
            "-r1",
            ".r1",
            "_r1",
            "r 1",
            "r@1",
            "r#1",
            "r/1",
            "a" * 65,  # > 64 chars
        ],
    )
    def test_invalid_device_id(self, service: DeviceService, invalid_id: str):
        with pytest.raises(InvalidDeviceError, match="device_id"):
            service.create(device_id=invalid_id, host="10.0.0.1")

    @pytest.mark.parametrize(
        "valid_id",
        [
            "R1",
            "r1",
            "router-core-01",
            "switch_1.agg",
            "123Router",
            "a" * 64,
        ],
    )
    def test_valid_device_id(self, service: DeviceService, valid_id: str):
        dev = service.create(device_id=valid_id, host=f"10.0.{len(valid_id)}.1")
        assert dev.device_id == valid_id

    @pytest.mark.parametrize(
        "valid_host",
        [
            "192.168.1.1",
            "10.0.0.254",
            "2001:db8::1",
            "::1",
            "router.local",
            "r1.core.datacenter.corp",
            "router-1.example.com",
        ],
    )
    def test_valid_host(self, service: DeviceService, valid_host: str):
        dev = service.create(device_id=f"dev-{abs(hash(valid_host)) % 10000}", host=valid_host)
        assert dev.host == valid_host

    @pytest.mark.parametrize(
        "invalid_host",
        [
            "",
            "   ",
            "host with spaces",
            "host/with/slashes",
            "user@host",
            "host#1",
            "host?query",
            "-invalid.label",
            "invalid-.label",
            "a" * 254,  # > 253 chars
        ],
    )
    def test_invalid_host(self, service: DeviceService, invalid_host: str):
        with pytest.raises(InvalidDeviceError, match="[Hh]ost"):
            service.create(device_id="R1", host=invalid_host)

    @pytest.mark.parametrize("invalid_port", [0, -1, 65536, 100000])
    def test_invalid_port(self, service: DeviceService, invalid_port: int):
        with pytest.raises(InvalidDeviceError, match="[Pp]ort"):
            service.create(device_id="R1", host="10.0.0.1", port=invalid_port)

    @pytest.mark.parametrize("invalid_platform", ["juniper", "cisco_nxos", "arista", "linux"])
    def test_invalid_platform(self, service: DeviceService, invalid_platform: str):
        with pytest.raises(InvalidDeviceError, match="[Pp]latform"):
            service.create(device_id="R1", host="10.0.0.1", platform=invalid_platform)


class TestAllowedNetworksSSRF:
    @pytest.fixture
    def restricted_service(self, repo: SqliteDeviceRepository) -> DeviceService:
        allowed = [
            ipaddress.ip_network("10.0.0.0/16"),
            ipaddress.ip_network("192.168.1.0/24"),
            ipaddress.ip_network("2001:db8:1::/48"),
        ]
        return DeviceService(repo, allowed_networks=allowed)

    def test_ip_in_allowed_network_succeeds(self, restricted_service: DeviceService):
        dev1 = restricted_service.create("R1", "10.0.1.5")
        assert dev1.host == "10.0.1.5"

        dev2 = restricted_service.create("R2", "192.168.1.50")
        assert dev2.host == "192.168.1.50"

        dev3 = restricted_service.create("R3", "2001:db8:1::1")
        assert dev3.host == "2001:db8:1::1"

    def test_ip_outside_allowed_network_raises_error(self, restricted_service: DeviceService):
        with pytest.raises(InvalidDeviceError, match="not in any allowed network"):
            restricted_service.create("R1", "172.16.1.1")

        with pytest.raises(InvalidDeviceError, match="not in any allowed network"):
            restricted_service.create("R2", "8.8.8.8")

    def test_hostname_rejected_when_allowed_networks_configured(self, restricted_service: DeviceService):
        with pytest.raises(InvalidDeviceError, match="only IP addresses.*permitted"):
            restricted_service.create("R1", "router.internal.corp")


class TestDeviceCRUD:
    def test_get_device(self, service: DeviceService):
        service.create("R1", "10.0.0.1")
        dev = service.get("R1")
        assert dev.device_id == "R1"

    def test_get_nonexistent_raises_device_not_found(self, service: DeviceService):
        with pytest.raises(DeviceNotFoundError, match="not found"):
            service.get("NONEXISTENT")

    def test_list_devices(self, service: DeviceService):
        service.create("R2", "10.0.0.2")
        service.create("R1", "10.0.0.1")

        devices = service.list()
        assert len(devices) == 2
        assert [d.device_id for d in devices] == ["R1", "R2"]

    def test_delete_device(self, service: DeviceService):
        service.create("R1", "10.0.0.1")
        service.delete("R1")

        with pytest.raises(DeviceNotFoundError):
            service.get("R1")

    def test_delete_nonexistent_raises_device_not_found(self, service: DeviceService):
        with pytest.raises(DeviceNotFoundError, match="not found"):
            service.delete("NONEXISTENT")
