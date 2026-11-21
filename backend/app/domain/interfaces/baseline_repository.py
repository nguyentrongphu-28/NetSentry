"""Abstract interface for baseline repository."""

from __future__ import annotations

from typing import Protocol
from app.domain.entities.baseline import Baseline


class BaselineRepository(Protocol):
    def get_active(self, device_id: str) -> Baseline | None:
        """Get the active baseline for a device, or None if none set."""
        ...

    def list_history(self, device_id: str, limit: int = 50) -> list[Baseline]:
        """List baseline history for a device (newest first)."""
        ...

    def get_by_id(self, baseline_id: int) -> Baseline | None:
        """Get a specific baseline record by ID."""
        ...

    def is_snapshot_pinned(self, snapshot_id: int) -> bool:
        """Return True if the snapshot is referenced by any ACTIVE baseline."""
        ...

    def set_active_baseline(
        self,
        *,
        device_id: str,
        snapshot_id: int,
        content_sha256: str,
        approved_by: str,
        note: str | None,
        fail_count_at_approval: int,
    ) -> Baseline:
        """Retire current ACTIVE baseline (if any) and insert new ACTIVE baseline in a single transaction."""
        ...

    def retire_active(self, device_id: str, retired_by: str) -> Baseline | None:
        """Retire the current ACTIVE baseline for a device. Returns the retired baseline or None."""
        ...
