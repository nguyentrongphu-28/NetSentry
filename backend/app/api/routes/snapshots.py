"""API endpoints for configuration snapshots and config diff (Spec 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import (
    Principal,
    get_client_ip,
    get_device_service,
    get_diff_service,
    get_security_event_service,
    get_snapshot_service,
    require_role,
)
from app.api.schemas.snapshots import ConfigDiffOut, DiffHunkOut, DiffLineOut, SnapshotDetailOut, SnapshotOut
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.domain.errors import DiffInputError
from app.services.device_service import DeviceService
from app.services.diff_service import DiffService
from app.services.security_event_service import SecurityEventService
from app.services.snapshot_service import SnapshotService

router = APIRouter(tags=["Snapshots"])


@router.get(
    "/devices/{device_id}/snapshots",
    response_model=list[SnapshotOut],
    summary="List snapshot metadata for a device",
)
def list_snapshots(
    device_id: str,
    device_service: DeviceService = Depends(get_device_service),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
) -> list[SnapshotOut]:
    # Check device exists
    device_service.get(device_id)
    snapshots = snapshot_service.list_for_device(device_id)
    return [
        SnapshotOut(
            id=s.id,
            device_id=s.device_id,
            run_id=s.run_id,
            created_at=s.created_at,
            content_sha256=s.content_sha256,
            size_bytes=s.size_bytes,
            line_count=s.line_count,
            redaction_version=s.redaction_version,
        )
        for s in snapshots
    ]


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=SnapshotDetailOut,
    summary="Get snapshot metadata and redacted content",
)
def get_snapshot(
    snapshot_id: int,
    request: Request,
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
    security_event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR)),
) -> SnapshotDetailOut:
    meta, content = snapshot_service.read_content(snapshot_id)

    client_ip = get_client_ip(request)
    security_event_service.record(
        event_type=SecurityEventType.SNAPSHOT_VIEWED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=f"snapshot:{snapshot_id}",
        detail=f"Device {meta.device_id}, Run {meta.run_id}",
    )

    return SnapshotDetailOut(
        id=meta.id,
        device_id=meta.device_id,
        run_id=meta.run_id,
        created_at=meta.created_at,
        content_sha256=meta.content_sha256,
        size_bytes=meta.size_bytes,
        line_count=meta.line_count,
        redaction_version=meta.redaction_version,
        content=content,
    )


@router.delete(
    "/snapshots/{snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a single snapshot",
)
def delete_snapshot(
    snapshot_id: int,
    request: Request,
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
    security_event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.ADMIN)),
) -> Response:
    meta = snapshot_service.get_metadata(snapshot_id)
    snapshot_service.delete(snapshot_id)

    client_ip = get_client_ip(request)
    security_event_service.record(
        event_type=SecurityEventType.SNAPSHOT_DELETED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=f"snapshot:{snapshot_id}",
        detail=f"Deleted snapshot for device {meta.device_id}, run {meta.run_id}",
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/devices/{device_id}/diff",
    response_model=ConfigDiffOut,
    summary="Get configuration diff between two snapshots",
)
def get_device_config_diff(
    device_id: str,
    from_run: int | None = Query(None, description="Starting audit run ID (defaults to previous snapshot)"),
    to_run: int | None = Query(None, description="Ending audit run ID (defaults to latest snapshot)"),
    device_service: DeviceService = Depends(get_device_service),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
    diff_service: DiffService = Depends(get_diff_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR)),
) -> ConfigDiffOut:
    device_service.get(device_id)

    snapshots = snapshot_service.list_for_device(device_id)
    if len(snapshots) < 2 and (from_run is None or to_run is None):
        raise DiffInputError("At least two snapshots are required to perform a diff")

    if to_run is not None:
        to_snap = next((s for s in snapshots if s.run_id == to_run), None)
        if not to_snap:
            raise DiffInputError(f"Snapshot for to_run={to_run} not found for device {device_id}")
    else:
        to_snap = snapshots[0]

    if from_run is not None:
        from_snap = next((s for s in snapshots if s.run_id == from_run), None)
        if not from_snap:
            raise DiffInputError(f"Snapshot for from_run={from_run} not found for device {device_id}")
    else:
        # Pick the one immediately older than to_snap
        older_snaps = [s for s in snapshots if s.run_id < to_snap.run_id]
        if not older_snaps:
            raise DiffInputError(f"No previous snapshot found before run {to_snap.run_id}")
        from_snap = older_snaps[0]

    if from_snap.run_id == to_snap.run_id:
        raise DiffInputError("Cannot diff a snapshot against itself")

    # Read contents (enforces content API enabled check)
    _, from_content = snapshot_service.read_content(from_snap.id)
    _, to_content = snapshot_service.read_content(to_snap.id)

    diff_result = diff_service.config_diff(from_snap, to_snap, from_content, to_content)

    return ConfigDiffOut(
        from_run_id=diff_result.from_run_id,
        to_run_id=diff_result.to_run_id,
        identical=diff_result.identical,
        added=diff_result.added,
        removed=diff_result.removed,
        truncated=diff_result.truncated,
        hunks=[
            DiffHunkOut(
                old_start=h.old_start,
                new_start=h.new_start,
                lines=[DiffLineOut(op=ln.op, text=ln.text) for ln in h.lines],
            )
            for h in diff_result.hunks
        ],
    )
