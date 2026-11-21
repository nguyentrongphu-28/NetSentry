"""Service orchestrating device audits and execution locking."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Callable

from app.domain.entities.audit_result import AuditStatus
from app.domain.entities.audit_run import AuditRunDetail, AuditRunSummary
from app.domain.entities.device import Credentials
from app.domain.errors import (
    AuditAlreadyRunningError,
    AuditNotFoundError,
    CredentialsRequiredError,
    DeviceNotFoundError,
)
from app.domain.interfaces.audit_repository import AuditRepository
from app.domain.interfaces.device_repository import DeviceRepository
from app.services.audit_service import AuditService

if TYPE_CHECKING:
    from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)


class AuditRunService:
    """Coordinates running audits, preventing concurrent runs on the same device."""

    def __init__(
        self,
        device_repository: DeviceRepository,
        audit_repository: AuditRepository,
        audit_service: AuditService,
        *,
        snapshot_service: SnapshotService | None = None,
        default_credentials: Callable[[], Credentials | None] | None = None,
    ) -> None:
        self.device_repository = device_repository
        self.audit_repository = audit_repository
        self.audit_service = audit_service
        self.snapshot_service = snapshot_service
        self.default_credentials = default_credentials

        self._global_lock = threading.Lock()
        self._device_locks: dict[str, threading.Lock] = {}

    def _get_device_lock(self, device_id: str) -> threading.Lock:
        with self._global_lock:
            if device_id not in self._device_locks:
                self._device_locks[device_id] = threading.Lock()
            return self._device_locks[device_id]

    def run_audit(
        self,
        device_id: str,
        credentials: Credentials | None = None,
    ) -> AuditRunDetail:
        device = self.device_repository.get(device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        resolved_creds = credentials
        if resolved_creds is None and self.default_credentials is not None:
            resolved_creds = self.default_credentials()

        if resolved_creds is None:
            raise CredentialsRequiredError(
                f"Credentials required to audit device '{device_id}'"
            )

        dev_lock = self._get_device_lock(device_id)
        if not dev_lock.acquire(blocking=False):
            raise AuditAlreadyRunningError(
                f"An audit is already running for device '{device_id}'"
            )

        try:
            target = device.to_target()
            collected_config: str | None = None

            def _on_config(cfg: str) -> None:
                nonlocal collected_config
                collected_config = cfg

            result = self.audit_service.audit_device(
                target,
                resolved_creds,
                on_config_collected=_on_config,
            )
            run_id = self.audit_repository.save_run(result)

            if (
                result.status == AuditStatus.COMPLETED
                and collected_config is not None
                and self.snapshot_service is not None
            ):
                try:
                    self.snapshot_service.create_for_run(device_id, run_id, collected_config)
                except Exception as snap_exc:
                    logger.warning(
                        "Snapshot creation failed for device %s run %s: %s",
                        device_id,
                        run_id,
                        type(snap_exc).__name__,
                    )

            detail = self.audit_repository.get_run(run_id)
            if detail is None:
                raise RuntimeError(
                    f"Audit run '{run_id}' could not be retrieved after saving"
                )
            return detail
        finally:
            dev_lock.release()

    def get_run(self, run_id: int) -> AuditRunDetail:
        detail = self.audit_repository.get_run(run_id)
        if detail is None:
            raise AuditNotFoundError(f"Audit run '{run_id}' not found")
        return detail

    def list_runs(
        self, device_id: str, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[AuditRunSummary], int]:
        if self.device_repository.get(device_id) is None:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        return self.audit_repository.list_runs(device_id, limit=limit, offset=offset)

    def latest_run(self, device_id: str) -> AuditRunSummary | None:
        if self.device_repository.get(device_id) is None:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        return self.audit_repository.latest_run(device_id)
