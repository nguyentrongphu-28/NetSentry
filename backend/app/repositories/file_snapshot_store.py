from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from app.domain.interfaces.snapshot_file_store import SnapshotFileStore


class FileSnapshotStore(SnapshotFileStore):
    """Stores configuration snapshots as individual files on local filesystem."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self._ensure_dir(self.base_dir, 0o700)

    @staticmethod
    def _ensure_dir(path: Path, mode: int) -> None:
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            try:
                path.chmod(mode)
            except OSError:
                pass

    def _device_dir_name(self, device_id: str) -> str:
        # Hex hash of device_id avoids weird characters and path traversal
        return hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:16]

    def _resolve_safe(self, rel_path: str) -> Path:
        target = (self.base_dir / rel_path).resolve()
        try:
            target.relative_to(self.base_dir)
        except ValueError:
            raise ValueError(f"Path traversal detected: {rel_path}")
        return target

    def write(self, device_id: str, run_id: int, content: str) -> str:
        dir_name = self._device_dir_name(device_id)
        rel_file_name = f"{dir_name}/{run_id}.cfg"
        target_path = self._resolve_safe(rel_file_name)

        dev_dir = target_path.parent
        self._ensure_dir(dev_dir, 0o700)

        # Atomic write via temporary file in same directory
        fd, tmp_path_str = tempfile.mkstemp(prefix="tmp_snap_", dir=dev_dir)
        tmp_path = Path(tmp_path_str)
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            if os.name == "posix":
                try:
                    tmp_path.chmod(0o600)
                except OSError:
                    pass
            os.replace(tmp_path, target_path)
            if os.name == "posix":
                try:
                    target_path.chmod(0o600)
                except OSError:
                    pass
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

        return rel_file_name

    def read(self, file_name: str) -> str:
        target_path = self._resolve_safe(file_name)
        if not target_path.is_file():
            raise FileNotFoundError(f"Snapshot file not found: {file_name}")
        return target_path.read_text(encoding="utf-8")

    def delete_file(self, file_name: str) -> None:
        target_path = self._resolve_safe(file_name)
        if target_path.is_file():
            target_path.unlink()

    def delete_device_dir(self, device_id: str) -> None:
        dir_name = self._device_dir_name(device_id)
        target_dir = self._resolve_safe(dir_name)
        if target_dir.is_dir():
            shutil.rmtree(target_dir, ignore_errors=True)

    def cleanup_orphans(self, valid_file_names: set[str]) -> int:
        removed_count = 0
        if not self.base_dir.is_dir():
            return 0

        for path in self.base_dir.glob("*/*.cfg"):
            rel_name = f"{path.parent.name}/{path.name}"
            if rel_name not in valid_file_names:
                try:
                    path.unlink()
                    removed_count += 1
                except OSError:
                    pass

        # Cleanup empty subdirectories
        for sub in self.base_dir.iterdir():
            if sub.is_dir() and not any(sub.iterdir()):
                try:
                    sub.rmdir()
                except OSError:
                    pass

        return removed_count
