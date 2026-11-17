"""Abstract base interface for network device connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DeviceConnector(ABC):
    """Abstract interface defining required operations on target network devices."""

    platform: str

    @abstractmethod
    def connect(self) -> None:
        """Establish connection with the target device."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Close connection with the target device. Must be idempotent and never raise."""
        raise NotImplementedError

    @abstractmethod
    def get_running_config(self) -> str:
        """Retrieve the device's running configuration."""
        raise NotImplementedError

    @abstractmethod
    def get_hostname(self) -> str:
        """Retrieve the configured hostname of the device."""
        raise NotImplementedError

    def __enter__(self) -> DeviceConnector:
        try:
            self.connect()
            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
