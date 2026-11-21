"""Baseline management and drift reporting service."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Callable

from app.domain.entities.baseline import Baseline
from app.domain.entities.drift import DriftReport, DriftSummary
from app.domain.errors import (
    BaselineDisabledError,
    BaselineFailuresNotConfirmedError,
    BaselineNotFoundError,
    DiffInputError,
    SnapshotNotFoundError,
)
from app.domain.interfaces.baseline_repository import BaselineRepository
from app.domain.interfaces.drift_repository import DriftRepository
from app.services.drift_service import DriftService
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)


class BaselineService:
    """Coordinates approval, retirement of baselines and drift reporting."""

    def __init__(
        self,
        baseline_repository: BaselineRepository,
        drift_repository: DriftRepository,
        snapshot_service: SnapshotService,
        drift_service: DriftService,
        audit_run_repository: object,  # SQLiteAuditRunRepository protocol
        *,
        enabled: bool = True,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.baseline_repository = baseline_repository
        self.drift_repository = drift_repository
        self.snapshot_service = snapshot_service
        self.drift_service = drift_service
        self.audit_run_repository = audit_run_repository
        self.enabled = enabled
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise BaselineDisabledError("Baseline and drift features are disabled")

    def approve(
        self,
        *,
        device_id: str,
        snapshot_id: int,
        approved_by: str,
        note: str | None = None,
        confirm_with_failures: bool = False,
    ) -> Baseline:
        """Approve a snapshot as the active baseline for a device."""
        self._ensure_enabled()

        # 1. Validate snapshot belongs to device
        try:
            snapshot = self.snapshot_service.get_metadata(snapshot_id)
        except SnapshotNotFoundError:
            raise DiffInputError(f"Snapshot '{snapshot_id}' not found") from None

        if snapshot.device_id != device_id:
            raise DiffInputError(f"Snapshot '{snapshot_id}' does not belong to device '{device_id}'")

        # 2. Validate audit run is COMPLETED
        run_detail = self.audit_run_repository.get_run(snapshot.run_id)
        if run_detail is None or run_detail.summary.status.value != "COMPLETED":
            raise DiffInputError(f"Audit run '{snapshot.run_id}' is not in COMPLETED status")

        # 3. Check for failures
        fail_count = run_detail.summary.fail_count
        if fail_count > 0 and not confirm_with_failures:
            raise BaselineFailuresNotConfirmedError(
                f"Snapshot audit run has {fail_count} failure(s). Explicit confirmation required.",
                fail_count=fail_count,
            )

        # 4. Clean note
        clean_note = note.strip()[:200] if note else None
        if clean_note:
            # Strip control characters
            clean_note = "".join(ch for ch in clean_note if ch >= " " or ch in "\t\n\r")

        # 5. Atomic set active baseline in repository
        return self.baseline_repository.set_active_baseline(
            device_id=device_id,
            snapshot_id=snapshot_id,
            content_sha256=snapshot.content_sha256,
            approved_by=approved_by,
            note=clean_note,
            fail_count_at_approval=fail_count,
        )

    def retire(self, device_id: str, retired_by: str) -> Baseline:
        """Retire the current active baseline for a device."""
        self._ensure_enabled()
        baseline = self.baseline_repository.retire_active(device_id, retired_by)
        if baseline is None:
            raise BaselineNotFoundError(f"No active baseline found for device '{device_id}'")
        return baseline

    def get_active(self, device_id: str) -> Baseline:
        """Get active baseline for device."""
        self._ensure_enabled()
        baseline = self.baseline_repository.get_active(device_id)
        if baseline is None:
            raise BaselineNotFoundError(f"No active baseline found for device '{device_id}'")
        return baseline

    def list_history(self, device_id: str, limit: int = 50) -> list[Baseline]:
        """List baseline history."""
        self._ensure_enabled()
        return self.baseline_repository.list_history(device_id, limit=limit)

    def is_pinned(self, snapshot_id: int) -> bool:
        """Check if snapshot is pinned by an ACTIVE baseline."""
        return self.baseline_repository.is_snapshot_pinned(snapshot_id)

    def drift_for_run(
        self,
        device_id: str,
        run_id: int,
        detail: bool = False,
    ) -> DriftReport:
        """Calculate or fetch drift report for a run against the active baseline."""
        self._ensure_enabled()

        baseline = self.baseline_repository.get_active(device_id)
        if baseline is None:
            raise BaselineNotFoundError(f"No active baseline found for device '{device_id}'")

        # Read baseline and current snapshot files directly via repository & filestore
        base_meta = self.snapshot_service.snapshot_repository.get(baseline.snapshot_id)
        if base_meta is None:
            raise SnapshotNotFoundError(f"Baseline snapshot '{baseline.snapshot_id}' file is missing")

        curr_meta = self.snapshot_service.snapshot_repository.get_by_run_id(run_id)
        if curr_meta is None:
            raise DiffInputError(f"No snapshot found for audit run '{run_id}'")

        baseline_content = self.snapshot_service.file_store.read(base_meta[1])
        current_content = self.snapshot_service.file_store.read(curr_meta[1])

        return self.drift_service.compare(
            device_id=device_id,
            baseline_id=baseline.id,
            run_id=run_id,
            baseline_text=baseline_content,
            current_text=current_content,
            include_lines=detail,
        )

    def compute_and_store_summary(self, device_id: str, run_id: int) -> DriftSummary | None:
        """Compute and persist drift summary for completed audit run if baseline exists."""
        if not self.enabled:
            return None

        baseline = self.baseline_repository.get_active(device_id)
        if baseline is None:
            return None

        try:
            # Note: For internal summary computation, bypass ContentDisabledError check if needed
            # read_content directly via repository/filestore
            base_meta = self.snapshot_service.snapshot_repository.get(baseline.snapshot_id)
            curr_meta = self.snapshot_service.snapshot_repository.get_by_run_id(run_id)
            if not base_meta or not curr_meta:
                return None

            base_content = self.snapshot_service.file_store.read(base_meta[1])
            curr_content = self.snapshot_service.file_store.read(curr_meta[1])

            report = self.drift_service.compare(
                device_id=device_id,
                baseline_id=baseline.id,
                run_id=run_id,
                baseline_text=base_content,
                current_text=curr_content,
                include_lines=False,
            )

            now_iso = self.clock().isoformat()
            self.drift_repository.save_summary(
                run_id=run_id,
                device_id=device_id,
                baseline_id=baseline.id,
                checked_at=now_iso,
                summary=report.summary,
            )
            return report.summary
        except Exception as exc:
            logger.warning(
                "Failed to compute and store drift summary for device %s run %s: %s",
                device_id,
                run_id,
                type(exc).__name__,
            )
            return None
