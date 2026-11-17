"""Abstract interface for audit repository."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.audit_result import AuditResult
from app.domain.entities.audit_run import AuditRunDetail, AuditRunSummary


class AuditRepository(ABC):
    """Abstract contract for persisting and querying audit runs."""

    @abstractmethod
    def save_run(self, result: AuditResult) -> int:
        """Persist an audit result and all its findings in one transaction.

        Returns the new run_id.
        Raises DeviceNotFoundError if result.device_id is not in the devices table.
        """
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: int) -> AuditRunDetail | None:
        """Return full detail for the given run_id, or None if not found."""
        raise NotImplementedError

    @abstractmethod
    def list_runs(
        self, device_id: str, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[AuditRunSummary], int]:
        """Return (items, total) for the device; newest runs first.

        limit is clamped to [1, 200]; offset must be >= 0.
        """
        raise NotImplementedError

    @abstractmethod
    def latest_run(self, device_id: str) -> AuditRunSummary | None:
        """Return the most recent AuditRunSummary for the device, or None."""
        raise NotImplementedError
