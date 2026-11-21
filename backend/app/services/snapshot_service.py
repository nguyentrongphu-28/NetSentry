from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
from typing import Callable

from app.domain.entities.snapshot import ConfigSnapshot
from app.domain.errors import ContentDisabledError, SnapshotNotFoundError
from app.domain.interfaces.snapshot_file_store import SnapshotFileStore
from app.domain.interfaces.snapshot_repository import SnapshotRepository
from app.security.config_normalizer import ConfigNormalizer
from app.security.config_redactor import ConfigRedactor, REDACTION_VERSION

logger = logging.getLogger(__name__)


class SnapshotService:
    """Manages the lifecycle of configuration snapshots."""

    def __init__(
        self,
        snapshot_repository: SnapshotRepository,
        file_store: SnapshotFileStore,
        redactor: ConfigRedactor,
        normalizer: type[ConfigNormalizer] = ConfigNormalizer,
        *,
        enabled: bool = True,
        keep: int = 30,
        content_api_enabled: bool = True,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.snapshot_repository = snapshot_repository
        self.file_store = file_store
        self.redactor = redactor
        self.normalizer = normalizer
        self.enabled = enabled
        self.keep = max(1, min(500, keep))
        self.content_api_enabled = content_api_enabled
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def create_for_run(
        self,
        device_id: str,
        run_id: int,
        raw_config: str,
    ) -> ConfigSnapshot | None:
        """Create and store a redacted snapshot for a completed audit run."""
        if not self.enabled:
            return None

        # Redact secrets before anything touches disk or database
        redacted = self.redactor.redact(raw_config)
        normalized = self.normalizer.normalize(redacted)

        content_bytes = normalized.encode("utf-8")
        content_sha256 = hashlib.sha256(content_bytes).hexdigest()
        size_bytes = len(content_bytes)
        line_count = len(normalized.splitlines())

        # Write to disk with 0600 permissions
        file_name = self.file_store.write(device_id, run_id, normalized)

        snapshot = ConfigSnapshot(
            id=0,
            device_id=device_id,
            run_id=run_id,
            created_at=self.clock(),
            content_sha256=content_sha256,
            size_bytes=size_bytes,
            line_count=line_count,
            redaction_version=REDACTION_VERSION,
        )

        saved = self.snapshot_repository.save(snapshot, file_name)

        # Enforce retention policy
        try:
            removed_files = self.snapshot_repository.enforce_retention(device_id, self.keep)
            for f in removed_files:
                self.file_store.delete_file(f)
        except Exception as ret_exc:
            logger.warning(
                "Snapshot retention enforcement failed for device %s: %s",
                device_id,
                type(ret_exc).__name__,
            )

        return saved

    def list_for_device(self, device_id: str, limit: int = 30) -> list[ConfigSnapshot]:
        return self.snapshot_repository.list_for_device(device_id, limit=limit)

    def get_metadata(self, snapshot_id: int) -> ConfigSnapshot:
        item = self.snapshot_repository.get(snapshot_id)
        if item is None:
            raise SnapshotNotFoundError(f"Snapshot '{snapshot_id}' not found")
        return item[0]

    def get_metadata_by_run_id(self, run_id: int) -> ConfigSnapshot:
        item = self.snapshot_repository.get_by_run_id(run_id)
        if item is None:
            raise SnapshotNotFoundError(f"Snapshot for audit run '{run_id}' not found")
        return item[0]

    def read_content(self, snapshot_id: int) -> tuple[ConfigSnapshot, str]:
        if not self.content_api_enabled:
            raise ContentDisabledError("Viewing snapshot content is disabled in public mode")

        item = self.snapshot_repository.get(snapshot_id)
        if item is None:
            raise SnapshotNotFoundError(f"Snapshot '{snapshot_id}' not found")
        snapshot, file_name = item
        content = self.file_store.read(file_name)
        return snapshot, content

    def read_content_by_run_id(self, run_id: int) -> tuple[ConfigSnapshot, str]:
        if not self.content_api_enabled:
            raise ContentDisabledError("Viewing snapshot content is disabled in public mode")

        item = self.snapshot_repository.get_by_run_id(run_id)
        if item is None:
            raise SnapshotNotFoundError(f"Snapshot for audit run '{run_id}' not found")
        snapshot, file_name = item
        content = self.file_store.read(file_name)
        return snapshot, content

    def delete(self, snapshot_id: int) -> None:
        file_name = self.snapshot_repository.delete(snapshot_id)
        if file_name is None:
            raise SnapshotNotFoundError(f"Snapshot '{snapshot_id}' not found")
        self.file_store.delete_file(file_name)

    def delete_for_device(self, device_id: str) -> None:
        self.snapshot_repository.delete_for_device(device_id)
        self.file_store.delete_device_dir(device_id)
