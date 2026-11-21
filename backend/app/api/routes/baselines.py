"""Baseline and Drift API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from app.api.deps import (
    Principal,
    get_baseline_service,
    get_client_ip,
    get_security_event_service,
    require_role,
)
from app.api.schemas.baselines import (
    ApproveBaselineIn,
    BaselineOut,
    BlockChangeOut,
    DriftHistoryItemOut,
    DriftReportOut,
    DriftSummaryOut,
)
from app.domain.entities.baseline import Baseline
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.domain.errors import ContentDisabledError
from app.services.baseline_service import BaselineService
from app.services.security_event_service import SecurityEventService

router = APIRouter(prefix="/devices/{device_id}", tags=["baselines"])


def _baseline_to_out(b: Baseline) -> BaselineOut:
    return BaselineOut(
        id=b.id,
        device_id=b.device_id,
        snapshot_id=b.snapshot_id,
        content_sha256=b.content_sha256,
        status=b.status.value,
        approved_by=b.approved_by,
        approved_at=b.approved_at.isoformat(),
        note=b.note,
        fail_count_at_approval=b.fail_count_at_approval,
        retired_at=b.retired_at.isoformat() if b.retired_at else None,
        retired_by=b.retired_by,
    )


@router.get("/baseline", response_model=BaselineOut)
def get_active_baseline(
    device_id: str,
    baseline_service: BaselineService = Depends(get_baseline_service),
    _: Principal = Depends(require_role(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> BaselineOut:
    """Get active baseline for a device."""
    baseline = baseline_service.get_active(device_id)
    return _baseline_to_out(baseline)


@router.get("/baselines", response_model=list[BaselineOut])
def list_baselines_history(
    device_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    baseline_service: BaselineService = Depends(get_baseline_service),
    _: Principal = Depends(require_role(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> list[BaselineOut]:
    """List baseline history for a device (newest first)."""
    items = baseline_service.list_history(device_id, limit=limit)
    return [_baseline_to_out(b) for b in items]


@router.post("/baseline", response_model=BaselineOut, status_code=status.HTTP_201_CREATED)
def approve_baseline(
    device_id: str,
    payload: ApproveBaselineIn,
    request: Request,
    baseline_service: BaselineService = Depends(get_baseline_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.ADMIN)),
) -> BaselineOut:
    """Approve snapshot as the active baseline for a device (Admin only)."""
    baseline = baseline_service.approve(
        device_id=device_id,
        snapshot_id=payload.snapshot_id,
        approved_by=principal.username,
        note=payload.note,
        confirm_with_failures=payload.confirm_with_failures,
    )

    client_ip = get_client_ip(request)
    event_service.record(
        event_type=SecurityEventType.BASELINE_APPROVED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=f"{device_id}:baseline:{baseline.id}",
        detail=f"Approved snapshot {payload.snapshot_id} as baseline (fails: {baseline.fail_count_at_approval})",
    )
    return _baseline_to_out(baseline)


@router.delete("/baseline", status_code=status.HTTP_204_NO_CONTENT)
def retire_active_baseline(
    device_id: str,
    request: Request,
    baseline_service: BaselineService = Depends(get_baseline_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.ADMIN)),
) -> None:
    """Retire the active baseline for a device (Admin only)."""
    retired = baseline_service.retire(device_id, principal.username)

    client_ip = get_client_ip(request)
    event_service.record(
        event_type=SecurityEventType.BASELINE_RETIRED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=f"{device_id}:baseline:{retired.id}",
        detail=f"Retired active baseline {retired.id}",
    )


@router.get("/drift", response_model=DriftReportOut)
def get_device_drift(
    device_id: str,
    request: Request,
    run_id: int | None = Query(default=None, description="Audit run ID (defaults to latest)"),
    detail: bool = Query(default=False, description="Include changed lines (requires operator+)"),
    baseline_service: BaselineService = Depends(get_baseline_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> DriftReportOut:
    """Get drift report for an audit run against the active baseline."""
    # If run_id not provided, resolve to latest audit run for device
    target_run_id = run_id
    if target_run_id is None:
        latest = baseline_service.audit_run_repository.latest_run(device_id)
        if latest is None:
            from app.domain.errors import AuditNotFoundError
            raise AuditNotFoundError(f"No audit runs found for device '{device_id}'")
        target_run_id = latest.id

    # If detail is requested, enforce operator role and content API availability
    if detail:
        if principal.role not in (Role.OPERATOR, Role.ADMIN):
            from app.domain.errors import ForbiddenError
            raise ForbiddenError("Viewing detailed drift lines requires operator role or above")

        if not baseline_service.snapshot_service.content_api_enabled:
            raise ContentDisabledError("Viewing configuration drift lines is disabled in public mode")

        # Record SNAPSHOT_VIEWED event for detailed view
        client_ip = get_client_ip(request)
        event_service.record(
            event_type=SecurityEventType.SNAPSHOT_VIEWED,
            actor_username=principal.username,
            client_ip=client_ip,
            target=f"{device_id}:drift:{target_run_id}",
            detail="Viewed detailed drift diff lines",
        )

    report = baseline_service.drift_for_run(
        device_id=device_id,
        run_id=target_run_id,
        detail=detail,
    )

    blocks_out: list[BlockChangeOut] = []
    for b in report.blocks:
        blocks_out.append(
            BlockChangeOut(
                key=b.key,
                kind=b.kind.value,
                security_relevant=b.security_relevant,
                added_lines=list(b.added_lines),
                removed_lines=list(b.removed_lines),
                added_count=b.added_count,
                removed_count=b.removed_count,
            )
        )

    return DriftReportOut(
        device_id=report.device_id,
        baseline_id=report.baseline_id,
        run_id=report.run_id,
        lines_included=report.lines_included,
        summary=DriftSummaryOut(
            status=report.summary.status,
            added_blocks=report.summary.added_blocks,
            removed_blocks=report.summary.removed_blocks,
            changed_blocks=report.summary.changed_blocks,
            security_relevant_count=report.summary.security_relevant_count,
        ),
        blocks=blocks_out,
        truncated=report.truncated,
    )


@router.get("/drift/history", response_model=list[DriftHistoryItemOut])
def get_drift_history(
    device_id: str,
    limit: int = Query(default=30, ge=1, le=200),
    baseline_service: BaselineService = Depends(get_baseline_service),
    _: Principal = Depends(require_role(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> list[DriftHistoryItemOut]:
    """Get drift history for a device (newest first)."""
    items = baseline_service.drift_repository.list_history(device_id, limit=limit)
    out: list[DriftHistoryItemOut] = []
    for it in items:
        out.append(
            DriftHistoryItemOut(
                run_id=int(it["run_id"]),
                device_id=str(it["device_id"]),
                baseline_id=int(it["baseline_id"]),
                checked_at=str(it["checked_at"]),
                status=str(it["status"]),  # type: ignore[arg-type]
                added_blocks=int(it["added_blocks"]),
                removed_blocks=int(it["removed_blocks"]),
                changed_blocks=int(it["changed_blocks"]),
                security_relevant_count=int(it["security_relevant_count"]),
            )
        )
    return out
