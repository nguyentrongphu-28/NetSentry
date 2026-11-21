from __future__ import annotations

from abc import ABC, abstractmethod


class SnapshotFileStore(ABC):
    """Abstract interface for storing snapshot files on disk."""

    @abstractmethod
    def write(self, device_id: str, run_id: int, content: str) -> str:
        """Atomically write redacted config with 0600 permissions; return relative file_name."""
        ...

    @abstractmethod
    def read(self, file_name: str) -> str:
        """Read snapshot content by its relative file_name."""
        ...

    @abstractmethod
    def delete_file(self, file_name: str) -> None:
        """Delete a single snapshot file if it exists."""
        ...

    @abstractmethod
    def delete_device_dir(self, device_id: str) -> None:
        """Delete all snapshot files and directory for a device."""
        ...

    @abstractmethod
    def cleanup_orphans(self, valid_file_names: set[str]) -> int:
        """Scan directory and remove files not present in valid_file_names; return count removed."""
        ...
