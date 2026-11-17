"""Factory for creating platform-specific device connectors."""

from __future__ import annotations

from typing import Callable

from app.domain.entities.device import Credentials, DeviceTarget
from app.domain.errors import UnsupportedPlatformError
from app.domain.interfaces.device_connector import DeviceConnector

ConnectorBuilder = Callable[[DeviceTarget, Credentials], DeviceConnector]


class ConnectorFactory:
    """Registry and factory for device connectors."""

    def __init__(self) -> None:
        self._builders: dict[str, ConnectorBuilder] = {}

    def register(self, platform: str, builder: ConnectorBuilder) -> None:
        """Register a builder function for a given platform name."""
        if platform in self._builders:
            raise ValueError(f"Platform '{platform}' is already registered")
        self._builders[platform] = builder

    def create(self, target: DeviceTarget, credentials: Credentials) -> DeviceConnector:
        """Create a connector for the target device."""
        builder = self._builders.get(target.platform)
        if builder is None:
            raise UnsupportedPlatformError(
                f"Unsupported platform: '{target.platform}'",
                host=target.host,
            )
        return builder(target, credentials)


def build_default_connector_factory() -> ConnectorFactory:
    """Build and return a ConnectorFactory configured with default platform connectors."""
    factory = ConnectorFactory()
    from app.connectors.cisco_ios_connector import CiscoIOSConnector

    factory.register("cisco_ios", lambda target, creds: CiscoIOSConnector(target, creds))
    return factory
