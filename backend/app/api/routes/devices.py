"""Device management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    Principal,
    get_audit_run_service,
    get_client_ip,
    get_device_service,
    get_security_event_service,
    get_snapshot_service,
    require_role,
)
from app.api.schemas.common import ErrorResponse
from app.api.schemas.device import (
    DeviceCreate,
    DeviceListOut,
    DeviceOut,
    DeviceWithLatestAuditOut,
)
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.services.audit_run_service import AuditRunService
from app.services.device_service import DeviceService
from app.services.security_event_service import SecurityEventService
from app.services.snapshot_service import SnapshotService

router = APIRouter(
    prefix="/devices",
    tags=["devices"],
)


@router.post(
    "",
    response_model=DeviceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new device",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        409: {"model": ErrorResponse, "description": "Device already exists"},
        422: {"model": ErrorResponse, "description": "Validation error or invalid device"},
    },
)
def create_device(
    payload: DeviceCreate,
    request: Request,
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR)),
    device_service: DeviceService = Depends(get_device_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
) -> DeviceOut:
    device = device_service.create(
        device_id=payload.device_id,
        host=payload.host,
        name=payload.name,
        port=payload.port,
        platform=payload.platform,
    )
    client_ip = get_client_ip(request)
    event_service.record(
        event_type=SecurityEventType.DEVICE_CREATED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=device.device_id,
        detail=f"Device {device.device_id} created ({device.host}:{device.port})",
    )
    return DeviceOut.from_domain(device)


@router.get(
    "",
    response_model=DeviceListOut,
    summary="List all devices with their latest audit summary",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
)
def list_devices(
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
    device_service: DeviceService = Depends(get_device_service),
    audit_service: AuditRunService = Depends(get_audit_run_service),
) -> DeviceListOut:
    devices = device_service.list()
    items: list[DeviceWithLatestAuditOut] = []
    for d in devices:
        latest = audit_service.latest_run(d.device_id)
        items.append(DeviceWithLatestAuditOut.from_domain_with_audit(d, latest))
    return DeviceListOut(items=items)


@router.get(
    "/{device_id}",
    response_model=DeviceWithLatestAuditOut,
    summary="Get device details with latest audit summary",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Device not found"},
    },
)
def get_device(
    device_id: str,
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
    device_service: DeviceService = Depends(get_device_service),
    audit_service: AuditRunService = Depends(get_audit_run_service),
) -> DeviceWithLatestAuditOut:
    device = device_service.get(device_id)
    latest = audit_service.latest_run(device_id)
    return DeviceWithLatestAuditOut.from_domain_with_audit(device, latest)


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete device and all audit history",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Device not found"},
    },
)
def delete_device(
    device_id: str,
    request: Request,
    principal: Principal = Depends(require_role(Role.ADMIN)),
    device_service: DeviceService = Depends(get_device_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
) -> Response:
    device_service.delete(device_id)
    snapshot_service.delete_for_device(device_id)
    client_ip = get_client_ip(request)
    event_service.record(
        event_type=SecurityEventType.DEVICE_DELETED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=device_id,
        detail=f"Device {device_id} deleted",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
