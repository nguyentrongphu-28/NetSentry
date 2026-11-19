"""Audit execution and history endpoints."""

from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    Principal,
    get_audit_run_service,
    get_client_ip,
    get_security_event_service,
    get_settings,
    require_role,
)
from app.api.schemas.audit import (
    AuditRequest,
    AuditRunDetailOut,
    AuditRunListOut,
    AuditRunSummaryOut,
    FindingOut,
)
from app.api.schemas.common import ErrorResponse
from app.core.config import Settings
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.domain.errors import BodyCredentialsDisabledError
from app.services.audit_run_service import AuditRunService
from app.services.security_event_service import SecurityEventService

router = APIRouter(
    tags=["audits"],
)


@router.post(
    "/devices/{device_id}/audit",
    response_model=AuditRunDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger an audit for a device",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Device not found"},
        409: {"model": ErrorResponse, "description": "Audit already running"},
        422: {"model": ErrorResponse, "description": "Credentials required or validation error"},
    },
)
def run_device_audit(
    device_id: str,
    request: Request,
    payload: AuditRequest | None = None,
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR)),
    audit_service: AuditRunService = Depends(get_audit_run_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
    settings: Settings = Depends(get_settings),
) -> AuditRunDetailOut:
    # Check if body credentials are provided when disallowed (e.g. public mode)
    if payload and payload.credentials is not None:
        if not settings.allow_body_credentials:
            raise BodyCredentialsDisabledError(
                "Providing credentials in the request body is disabled on this server."
            )

    creds = payload.credentials.to_domain() if payload and payload.credentials else None
    detail = audit_service.run_audit(device_id, credentials=creds)

    client_ip = get_client_ip(request)
    event_service.record(
        event_type=SecurityEventType.AUDIT_STARTED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=device_id,
        detail=f"Audit run #{detail.summary.id} started (status={detail.summary.status.value})",
    )

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
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
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
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
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
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
    audit_service: AuditRunService = Depends(get_audit_run_service),
) -> list[FindingOut]:
    detail = audit_service.get_run(run_id)
    findings = detail.findings

    if status is not None:
        findings = tuple(f for f in findings if (f.status.value if hasattr(f.status, "value") else str(f.status)) == status)
    if severity is not None:
        findings = tuple(f for f in findings if (f.severity.value if hasattr(f.severity, "value") else str(f.severity)) == severity)

    return [FindingOut.from_domain(f) for f in findings]
