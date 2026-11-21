"""API endpoints for audit run compare / findings diff (Spec 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    Principal,
    get_audit_run_service,
    get_diff_service,
    require_role,
)
from app.api.schemas.compare import CompareOut, FindingChangeOut
from app.domain.entities.user import Role
from app.domain.errors import AuditNotFoundError, DiffInputError
from app.services.audit_run_service import AuditRunService
from app.services.diff_service import DiffService

router = APIRouter(tags=["Compare"])


@router.get(
    "/audits/{run_id}/compare",
    response_model=CompareOut,
    summary="Compare findings of an audit run with a previous run",
)
def compare_audit_runs(
    run_id: int,
    with_run: int | None = Query(None, alias="with", description="Target audit run ID to compare against"),
    audit_service: AuditRunService = Depends(get_audit_run_service),
    diff_service: DiffService = Depends(get_diff_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
) -> CompareOut:
    to_run = audit_service.get_run(run_id)
    if not to_run:
        raise AuditNotFoundError(f"Audit run {run_id} not found")

    device_id = to_run.summary.device_id

    from_run = None
    if with_run is not None:
        from_run = audit_service.get_run(with_run)
        if not from_run:
            raise AuditNotFoundError(f"Comparison audit run {with_run} not found")
        if from_run.summary.device_id != device_id:
            raise DiffInputError(f"Audit runs belong to different devices: {from_run.summary.device_id} vs {device_id}")
        if from_run.summary.id == to_run.summary.id:
            raise DiffInputError("Cannot compare an audit run with itself")
    else:
        # Default: find the previous COMPLETED run for the same device
        history, _ = audit_service.list_runs(device_id, limit=50, offset=0)
        completed_prior = [
            r for r in history
            if r.status.value == "COMPLETED" and r.id < run_id
        ]
        if completed_prior:
            prev_id = completed_prior[0].id
            from_run = audit_service.get_run(prev_id)

    if from_run is None:
        # No previous completed run to compare against -> has_previous=False
        return CompareOut(
            from_run_id=None,
            to_run_id=run_id,
            device_id=device_id,
            has_previous=False,
            changes=[],
            counts={},
        )

    diff_result = diff_service.findings_diff(from_run, to_run)

    return CompareOut(
        from_run_id=diff_result.from_run_id,
        to_run_id=diff_result.to_run_id,
        device_id=diff_result.device_id,
        has_previous=True,
        changes=[
            FindingChangeOut(
                rule_id=c.rule_id,
                title=c.title,
                before_status=c.before_status,
                after_status=c.after_status,
                before_severity=c.before_severity,
                after_severity=c.after_severity,
                kind=c.kind,
            )
            for c in diff_result.changes
        ],
        counts={k.value: v for k, v in diff_result.counts.items()},
    )
