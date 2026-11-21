"""Factory for creating device configuration writers based on platform."""

from __future__ import annotations

from typing import Any, Callable

from app.connectors.cisco_ios_writer import CiscoIOSConfigWriter
from app.domain.errors import WriteAuthFailedError
from app.domain.interfaces.config_writer import ConfigWriter, ConfigWriterFactory


class DefaultConfigWriterFactory(ConfigWriterFactory):
    """Produces platform-specific ConfigWriter implementations using dedicated write credentials."""

    def __init__(
        self,
        write_username: str,
        write_password: str,
        write_enable_secret: str = "",
        *,
        timeout: int = 60,
        session_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.write_username = write_username
        self.write_password = write_password
        self.write_enable_secret = write_enable_secret
        self.timeout = timeout
        self.session_factory = session_factory

    def create_writer(
        self,
        device_id: str,
        host: str,
        port: int,
        platform: str,
    ) -> ConfigWriter:
        if not self.write_username or not self.write_password:
            raise WriteAuthFailedError(
                f"Dedicated write credentials not configured on server for device {device_id}"
            )

        if platform == "cisco_ios":
            return CiscoIOSConfigWriter(
                host=host,
                port=port,
                username=self.write_username,
                password=self.write_password,
                enable_secret=self.write_enable_secret,
                timeout=self.timeout,
                session_factory=self.session_factory,
            )

        raise ValueError(f"Unsupported platform for configuration writer: {platform!r}")
