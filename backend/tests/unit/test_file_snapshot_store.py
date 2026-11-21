from __future__ import annotations

import os
from pathlib import Path
import pytest

from app.repositories.file_snapshot_store import FileSnapshotStore


def test_file_snapshot_store_write_and_read(tmp_path: Path):
    store = FileSnapshotStore(tmp_path)
    device_id = "r1-core"
    run_id = 42
    content = "hostname r1-core\ninterface Gi0/0\n"

    file_name = store.write(device_id, run_id, content)
    assert file_name.endswith(f"{run_id}.cfg")

    # Read back
    read_back = store.read(file_name)
    assert read_back == content

    # Check file permissions on POSIX
    if os.name == "posix":
        full_path = tmp_path / file_name
        stat_mode = full_path.stat().st_mode & 0o777
        assert stat_mode == 0o600, f"Expected 0o600, got {oct(stat_mode)}"
        dir_mode = full_path.parent.stat().st_mode & 0o777
        assert dir_mode == 0o700, f"Expected 0o700, got {oct(dir_mode)}"


def test_file_snapshot_store_path_traversal(tmp_path: Path):
    store = FileSnapshotStore(tmp_path)

    # Malicious device_id attempting path traversal
    # Notice our store hashes device_id so device_id traversal is naturally mitigated,
    # but let's test if someone passes ../../ in file_name to read/delete
    with pytest.raises(ValueError, match="Path traversal detected"):
        store.read("../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        store.delete_file("../outside.cfg")


def test_file_snapshot_store_delete_and_cleanup_orphans(tmp_path: Path):
    store = FileSnapshotStore(tmp_path)

    f1 = store.write("dev-1", 101, "config 101")
    f2 = store.write("dev-1", 102, "config 102")
    f3 = store.write("dev-2", 201, "config 201")

    # Delete single file
    store.delete_file(f1)
    with pytest.raises(FileNotFoundError):
        store.read(f1)

    # Cleanup orphans: valid file is only f2
    removed = store.cleanup_orphans({f2})
    assert removed == 1  # f3 was orphaned
    assert (tmp_path / f2).exists()
    assert not (tmp_path / f3).exists()

    # Delete device dir
    store.delete_device_dir("dev-1")
    assert not (tmp_path / f2).exists()
