"""Abstract interface for drift repository."""

from __future__ import annotations

from typing import Protocol
from app.domain.entities.drift import DriftSummary


class DriftRepository(Protocol):
    def save_summary(
        self,
        *,
        run_id: int,
        device_id: str,
        baseline_id: int,
        checked_at: str,
        summary: DriftSummary,
    ) -> None:
        """Store drift summary result for an audit run."""
        ...

    def get_by_run(self, run_id: int) -> tuple[int, DriftSummary] | None:
        """Retrieve (baseline_id, DriftSummary) for a given run_id, or None."""
        ...

    def list_history(self, device_id: str, limit: int = 30) -> list[dict[str, object]]:
        """List drift history summaries for a device (newest first)."""
        ...
