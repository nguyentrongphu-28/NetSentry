"""Fake connector implementation for testing without real network devices."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.errors import NetSentryError
from app.domain.interfaces.device_connector import DeviceConnector


class FakeConnector(DeviceConnector):
    """Simulated connector returning predefined configuration text or raising planned errors."""

    platform: str = "cisco_ios"

    def __init__(
        self,
        config_text: str,
        hostname: str = "FAKE-R1",
        *,
        fail_on: type[NetSentryError] | None = None,
    ) -> None:
        self.config_text = config_text
        self.hostname = hostname
        self.fail_on = fail_on
        self.connect_calls: int = 0
        self.close_calls: int = 0
        self.is_connected: bool = False

    @classmethod
    def from_file(cls, path: str | Path, **kw: Any) -> FakeConnector:
        """Create a FakeConnector with configuration loaded from a file."""
        text = Path(path).read_text(encoding="utf-8")
        return cls(config_text=text, **kw)

    def connect(self) -> None:
        self.connect_calls += 1
        if self.fail_on is not None:
            raise self.fail_on("Simulated connector error")
        self.is_connected = True

    def close(self) -> None:
        self.close_calls += 1
        self.is_connected = False

    def get_running_config(self) -> str:
        return self.config_text

    def get_hostname(self) -> str:
        return self.hostname
