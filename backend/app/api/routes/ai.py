"""API endpoints for AI explanations (Spec 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import (
    Principal,
    get_ai_explain_service,
    get_client_ip,
    get_security_event_service,
    require_role,
)
from app.api.schemas.ai import (
    AiExplanationOut,
    AiStatusOut,
    PriorityItemOut,
    RiskNoteOut,
)
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.services.ai_explain_service import AiExplainService
from app.services.security_event_service import SecurityEventService

router = APIRouter(tags=["AI"])


@router.get(
    "/ai/status",
    response_model=AiStatusOut,
    summary="Check AI explanation service status",
)
def get_ai_status(
    ai_service: AiExplainService = Depends(get_ai_explain_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
) -> AiStatusOut:
    status_dict = ai_service.is_available()
    return AiStatusOut(
        enabled=bool(status_dict["enabled"]),
        reachable=bool(status_dict["reachable"]),
        model=str(status_dict["model"]),
    )


@router.post(
    "/audits/{run_id}/explain",
    response_model=AiExplanationOut,
    summary="Generate AI security explanation for an audit run",
)
def generate_audit_explanation(
    run_id: int,
    request: Request,
    force: bool = Query(False, description="Force re-generation bypassing cache"),
    ai_service: AiExplainService = Depends(get_ai_explain_service),
    security_event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR)),
) -> AiExplanationOut:
    explanation = ai_service.explain(run_id, username=principal.username, force=force)

    client_ip = get_client_ip(request)
    security_event_service.record(
        event_type=SecurityEventType.AI_EXPLAIN_REQUESTED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=f"audit:{run_id}",
        detail=f"AI explanation generated using model {explanation.model}",
    )

    return AiExplanationOut(
        run_id=explanation.run_id,
        created_at=explanation.created_at,
        model=explanation.model,
        prompt_version=explanation.prompt_version,
        input_sha256=explanation.input_sha256,
        summary=explanation.summary,
        priorities=[PriorityItemOut(rule_id=p.rule_id, reason=p.reason) for p in explanation.priorities],
        risks=[RiskNoteOut(rule_id=r.rule_id, warning=r.warning) for r in explanation.risks],
        generated_by_ai=True,
    )


@router.get(
    "/audits/{run_id}/explanation",
    response_model=AiExplanationOut,
    summary="Retrieve stored AI explanation for an audit run",
)
def get_audit_explanation(
    run_id: int,
    ai_service: AiExplainService = Depends(get_ai_explain_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
) -> AiExplanationOut:
    explanation = ai_service.get_explanation(run_id)
    return AiExplanationOut(
        run_id=explanation.run_id,
        created_at=explanation.created_at,
        model=explanation.model,
        prompt_version=explanation.prompt_version,
        input_sha256=explanation.input_sha256,
        summary=explanation.summary,
        priorities=[PriorityItemOut(rule_id=p.rule_id, reason=p.reason) for p in explanation.priorities],
        risks=[RiskNoteOut(rule_id=r.rule_id, warning=r.warning) for r in explanation.risks],
        generated_by_ai=True,
    )
