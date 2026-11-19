"""Security event log routes: /api/v1/security-events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import Principal, get_security_event_service, require_role
from app.api.schemas.security_events import SecurityEventOut
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.services.security_event_service import SecurityEventService

router = APIRouter(prefix="/security-events", tags=["security-events"])


@router.get("", response_model=list[SecurityEventOut])
async def list_security_events(
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    principal: Principal = Depends(require_role(Role.ADMIN)),
    event_service: SecurityEventService = Depends(get_security_event_service),
) -> list[SecurityEventOut]:
    """List security audit log events (Admin only)."""
    type_enum = SecurityEventType(event_type) if event_type else None
    events = event_service.list_events(
        limit=limit,
        before_id=before_id,
        event_type=type_enum,
    )
    return [
        SecurityEventOut(
            id=ev.id,
            occurred_at=ev.occurred_at,
            event_type=ev.event_type.value,
            actor_username=ev.actor_username,
            client_ip=ev.client_ip,
            target=ev.target,
            detail=ev.detail,
        )
        for ev in events
    ]
