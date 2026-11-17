"""Audit execution and history endpoints."""

from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_audit_run_service, require_api_key
from app.api.schemas.audit import (
    AuditRequest,
    AuditRunDetailOut,
    AuditRunListOut,
    AuditRunSummaryOut,
    FindingOut,
)
from app.api.schemas.common import ErrorResponse
from app.services.audit_run_service import AuditRunService

router = APIRouter(
    tags=["audits"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/devices/{device_id}/audit",
    response_model=AuditRunDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger an audit for a device",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"},
        409: {"model": ErrorResponse, "description": "Audit already running"},
        422: {"model": ErrorResponse, "description": "Credentials required or validation error"},
    },
)
def run_device_audit(
    device_id: str,
    payload: AuditRequest | None = None,
    audit_service: AuditRunService = Depends(get_audit_run_service),
) -> AuditRunDetailOut:
    creds = payload.credentials.to_domain() if payload and payload.credentials else None
    detail = audit_service.run_audit(device_id, credentials=creds)
    return AuditRunDetailOut.from_domain(detail)


@router.get(
    "/devices/{device_id}/audits",
    response_model=AuditRunListOut,
    summary="List audit history for a device",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"},
    },
)
def list_device_audits(
    device_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    audit_service: AuditRunService = Depends(get_audit_run_service),
) -> AuditRunListOut:
    items, total = audit_service.list_runs(device_id, limit=limit, offset=offset)
    return AuditRunListOut(
        items=[AuditRunSummaryOut.from_domain(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/audits/{run_id}",
    response_model=AuditRunDetailOut,
    summary="Get details of a specific audit run",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Audit not found"},
    },
)
def get_audit_run(
    run_id: int,
    audit_service: AuditRunService = Depends(get_audit_run_service),
) -> AuditRunDetailOut:
    detail = audit_service.get_run(run_id)
    return AuditRunDetailOut.from_domain(detail)


@router.get(
    "/audits/{run_id}/findings",
    response_model=list[FindingOut],
    summary="Get findings for a specific audit run with optional filtering",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Audit not found"},
        422: {"model": ErrorResponse, "description": "Invalid filter parameter"},
    },
)
def list_audit_findings(
    run_id: int,
    status: Literal["PASS", "FAIL", "UNKNOWN"] | None = Query(default=None),
    severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = Query(default=None),
    audit_service: AuditRunService = Depends(get_audit_run_service),
) -> list[FindingOut]:
    detail = audit_service.get_run(run_id)
    findings = detail.findings

    if status is not None:
        findings = tuple(f for f in findings if (f.status.value if hasattr(f.status, "value") else str(f.status)) == status)
    if severity is not None:
        findings = tuple(f for f in findings if (f.severity.value if hasattr(f.severity, "value") else str(f.severity)) == severity)

    return [FindingOut.from_domain(f) for f in findings]
