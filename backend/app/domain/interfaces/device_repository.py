"""Abstract interface for device repository."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.device import Device


class DeviceRepository(ABC):
    """Abstract contract for storing and retrieving devices."""

    @abstractmethod
    def add(self, device: Device) -> None:
        """Add a device to the repository.

        Raises DuplicateDeviceError if device_id or (host, port) already exists.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, device_id: str) -> Device | None:
        """Return the device with the given device_id, or None if not found."""
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[Device]:
        """Return all devices sorted by device_id ascending."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, device_id: str) -> bool:
        """Delete device and cascade-delete all related audit runs and findings.

        Returns True if a row was deleted, False if device_id was not found.
        """
        raise NotImplementedError
