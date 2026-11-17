"""Unit tests for ConnectorFactory."""

from __future__ import annotations

import pytest

from app.connectors.cisco_ios_connector import CiscoIOSConnector
from app.domain.entities.device import Credentials, DeviceTarget
from app.domain.errors import UnsupportedPlatformError
from app.domain.interfaces.device_connector import DeviceConnector
from app.factories.connector_factory import ConnectorFactory, build_default_connector_factory


class DummyConnector(DeviceConnector):
    platform = "dummy"

    def __init__(self, target: DeviceTarget, creds: Credentials) -> None:
        self.target = target
        self.creds = creds

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def get_running_config(self) -> str:
        return "dummy config"

    def get_hostname(self) -> str:
        return "DUMMY"


def test_connector_factory_register_and_create():
    factory = ConnectorFactory()
    factory.register("dummy", lambda target, creds: DummyConnector(target, creds))

    target = DeviceTarget(device_id="D1", host="192.168.1.10", platform="dummy")
    creds = Credentials(username="admin", password="password")

    connector = factory.create(target, creds)
    assert isinstance(connector, DummyConnector)
    assert connector.target == target
    assert connector.creds == creds


def test_connector_factory_register_duplicate_raises_value_error():
    factory = ConnectorFactory()
    factory.register("dummy", lambda t, c: DummyConnector(t, c))

    with pytest.raises(ValueError, match="already registered"):
        factory.register("dummy", lambda t, c: DummyConnector(t, c))


def test_connector_factory_unsupported_platform_raises_error():
    factory = ConnectorFactory()
    target = DeviceTarget(device_id="D1", host="192.168.1.10", platform="unknown_os")
    creds = Credentials(username="admin", password="password")

    with pytest.raises(UnsupportedPlatformError) as exc_info:
        factory.create(target, creds)

    assert exc_info.value.code == "UNSUPPORTED_PLATFORM"
    assert "unknown_os" in str(exc_info.value)


def test_build_default_connector_factory_creates_cisco_ios_connector():
    factory = build_default_connector_factory()
    target = DeviceTarget(device_id="R1", host="10.0.0.1", platform="cisco_ios")
    creds = Credentials(username="cisco", password="password")

    connector = factory.create(target, creds)
    assert isinstance(connector, CiscoIOSConnector)
    assert connector.target == target
    assert connector.credentials == creds

