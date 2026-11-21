from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.snapshot import ConfigSnapshot


class SnapshotRepository(ABC):
    """Abstract repository for storing snapshot metadata."""

    @abstractmethod
    def save(
        self,
        snapshot: ConfigSnapshot,
        file_name: str,
    ) -> ConfigSnapshot:
        """Save a new snapshot record and return it with assigned id."""
        ...

    @abstractmethod
    def get(self, snapshot_id: int) -> tuple[ConfigSnapshot, str] | None:
        """Get snapshot metadata and its relative file_name by ID."""
        ...

    @abstractmethod
    def get_by_run_id(self, run_id: int) -> tuple[ConfigSnapshot, str] | None:
        """Get snapshot metadata and its relative file_name by audit run_id."""
        ...

    @abstractmethod
    def list_for_device(self, device_id: str, limit: int = 30) -> list[ConfigSnapshot]:
        """List snapshots for a device ordered by created_at DESC."""
        ...

    @abstractmethod
    def delete(self, snapshot_id: int) -> str | None:
        """Delete a snapshot by ID and return its file_name, or None if not found."""
        ...

    @abstractmethod
    def delete_for_device(self, device_id: str) -> list[str]:
        """Delete all snapshots for a device and return their file_names."""
        ...

    @abstractmethod
    def enforce_retention(self, device_id: str, keep: int) -> list[str]:
        """Keep only the latest `keep` snapshots for a device; return file_names of removed ones."""
        ...

    @abstractmethod
    def list_all_file_names(self) -> set[str]:
        """List all registered snapshot file_names (used for orphan cleanup)."""
        ...
