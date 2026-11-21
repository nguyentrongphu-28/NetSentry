"""Remediation Plan API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import (
    Principal,
    get_client_ip,
    get_remediation_service,
    get_security_event_service,
    require_role,
)
from app.api.schemas.remediation import (
    ApprovePlanIn,
    ExpectedVerificationOut,
    ManualGuidanceOut,
    PlanEventOut,
    ProposePlanIn,
    RejectPlanIn,
    RemediationPlanDetailOut,
    RemediationPlanOut,
    RemediationTemplateOut,
    TemplatesResponseOut,
)
from app.domain.entities.remediation import PlanEvent, PlanStatus, RemediationPlan
from app.domain.entities.security_event import SecurityEventType
from app.domain.entities.user import Role
from app.remediation.templates import get_all_templates, get_manual_guidances, get_template
from app.services.remediation_service import RemediationService
from app.services.security_event_service import SecurityEventService

router = APIRouter(tags=["remediation"])


def _plan_to_out(plan: RemediationPlan) -> RemediationPlanOut:
    return RemediationPlanOut(
        id=plan.id,
        device_id=plan.device_id,
        run_id=plan.run_id,
        rule_id=plan.rule_id,
        status=plan.status.value,  # type: ignore[arg-type]
        risk_level=plan.risk_level.value,  # type: ignore[arg-type]
        persist_after_verify=plan.persist_after_verify,
        proposed_by=plan.proposed_by,
        proposed_at=plan.proposed_at.isoformat(),
        decided_by=plan.decided_by,
        decided_at=plan.decided_at.isoformat() if plan.decided_at else None,
        expires_at=plan.expires_at.isoformat(),
        plan_hash=plan.plan_hash,
    )


def _plan_to_detail_out(plan: RemediationPlan, timeline: list[PlanEvent]) -> RemediationPlanDetailOut:
    tmpl = get_template(plan.rule_id)
    return RemediationPlanDetailOut(
        id=plan.id,
        device_id=plan.device_id,
        run_id=plan.run_id,
        rule_id=plan.rule_id,
        status=plan.status.value,  # type: ignore[arg-type]
        risk_level=plan.risk_level.value,  # type: ignore[arg-type]
        persist_after_verify=plan.persist_after_verify,
        proposed_by=plan.proposed_by,
        proposed_at=plan.proposed_at.isoformat(),
        decided_by=plan.decided_by,
        decided_at=plan.decided_at.isoformat() if plan.decided_at else None,
        expires_at=plan.expires_at.isoformat(),
        plan_hash=plan.plan_hash,
        commands=list(plan.commands),
        impact=tmpl.impact_vi,
        risks="\n".join(tmpl.risks_vi),
        expected_verification=ExpectedVerificationOut(
            rule_id=tmpl.expected_verification[0],
            expected_status=tmpl.expected_verification[1],
        ),
        reversible=tmpl.reversible,
        rollback_note=tmpl.rollback_note_vi,
        decide_reason=plan.decision_reason,
        approved_hash_matches=(plan.approved_plan_hash == plan.plan_hash) if plan.approved_plan_hash else False,
        timeline=[
            PlanEventOut(
                id=e.id,
                plan_id=e.plan_id,
                occurred_at=e.occurred_at.isoformat(),
                actor=e.actor,
                event_type=e.event_type,
                detail=e.detail,
            )
            for e in timeline
        ],
    )


@router.get("/remediation/templates", response_model=TemplatesResponseOut)
def get_templates(
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
) -> TemplatesResponseOut:
    """List automated remediation templates and manual guidance for all rules."""
    templates = [
        RemediationTemplateOut(
            rule_id=t.rule_id,
            version=str(t.version),
            title=f"Khắc phục {t.rule_id}",
            commands=list(t.commands),
            risk_level=t.risk_level.value,  # type: ignore[arg-type]
            impact=t.impact_vi,
            risks="\n".join(t.risks_vi),
            reversible=t.reversible,
            rollback_note=t.rollback_note_vi,
            platforms=list(t.platforms),
        )
        for t in get_all_templates()
    ]
    manual_guidance = [
        ManualGuidanceOut(
            rule_id=g.rule_id,
            title=g.title,
            remediation_guide=g.remediation_hint,
            verification_guide=g.verification_hint,
            why_not_automated=g.reason_vi,
        )
        for g in get_manual_guidances()
    ]
    return TemplatesResponseOut(templates=templates, manual_guidance=manual_guidance)


@router.post(
    "/audits/{run_id}/findings/{rule_id}/remediation",
    response_model=RemediationPlanOut,
    status_code=status.HTTP_201_CREATED,
)
def propose_remediation_plan(
    run_id: int,
    rule_id: str,
    payload: ProposePlanIn,
    request: Request,
    response: Response,
    service: RemediationService = Depends(get_remediation_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR)),
) -> RemediationPlanOut:
    """Propose a remediation plan for a failing finding (Operator/Admin)."""
    client_ip = get_client_ip(request)
    plan = service.propose(
        run_id=run_id,
        rule_id=rule_id,
        proposer_username=principal.username,
        proposer_user_id=principal.user.id if principal.user else None,
        persist_after_verify=payload.persist_after_verify,
    )
    event_service.record(
        event_type=SecurityEventType.REMEDIATION_PROPOSED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=f"{plan.device_id}:{plan.rule_id}:{plan.id}",
        detail=f"Proposed remediation plan #{plan.id} for rule {plan.rule_id}",
    )
    response.headers["Location"] = f"/api/v1/remediation-plans/{plan.id}"
    return _plan_to_out(plan)


@router.get("/devices/{device_id}/remediation-plans", response_model=list[RemediationPlanOut])
def list_device_remediation_plans(
    device_id: str,
    status: str | None = Query(default=None),
    service: RemediationService = Depends(get_remediation_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
) -> list[RemediationPlanOut]:
    """List remediation plans for a device, optionally filtered by status."""
    plan_status: PlanStatus | None = None
    if status:
        try:
            plan_status = PlanStatus(status)
        except ValueError:
            return []
    plans = service.list_plans_for_device(device_id=device_id, status=plan_status)
    return [_plan_to_out(p) for p in plans]


@router.get("/remediation-plans/{plan_id}", response_model=RemediationPlanDetailOut)
def get_remediation_plan(
    plan_id: int,
    service: RemediationService = Depends(get_remediation_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
) -> RemediationPlanDetailOut:
    """Get full remediation plan details including command preview and timeline."""
    plan = service.get_plan(plan_id)
    timeline = service.list_events_for_plan(plan_id)
    return _plan_to_detail_out(plan, timeline)


@router.post("/remediation-plans/{plan_id}/approve", response_model=RemediationPlanDetailOut)
def approve_remediation_plan(
    plan_id: int,
    payload: ApprovePlanIn,
    request: Request,
    service: RemediationService = Depends(get_remediation_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.ADMIN)),
) -> RemediationPlanDetailOut:
    """Approve a remediation plan with step-up re-authentication (Admin only)."""
    client_ip = get_client_ip(request)
    plan = service.approve(
        plan_id=plan_id,
        approver_username=principal.username,
        approver_user_id=principal.user.id if principal.user else None,
        approver_role=principal.role,
        password=payload.password,
        client_ip=client_ip,
    )
    timeline = service.list_events_for_plan(plan_id)
    event_service.record(
        event_type=SecurityEventType.REMEDIATION_APPROVED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=f"{plan.device_id}:{plan.rule_id}:{plan.id}",
        detail=f"Approved remediation plan #{plan.id}",
    )
    return _plan_to_detail_out(plan, timeline)


@router.post("/remediation-plans/{plan_id}/reject", response_model=RemediationPlanDetailOut)
def reject_remediation_plan(
    plan_id: int,
    payload: RejectPlanIn,
    request: Request,
    service: RemediationService = Depends(get_remediation_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.ADMIN)),
) -> RemediationPlanDetailOut:
    """Reject a proposed remediation plan (Admin only)."""
    client_ip = get_client_ip(request)
    plan = service.reject(
        plan_id=plan_id,
        actor_username=principal.username,
        actor_user_id=principal.user.id if principal.user else None,
        actor_role=principal.role,
        reason=payload.reason,
        client_ip=client_ip,
    )
    timeline = service.list_events_for_plan(plan_id)
    event_service.record(
        event_type=SecurityEventType.REMEDIATION_REJECTED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=f"{plan.device_id}:{plan.rule_id}:{plan.id}",
        detail=f"Rejected remediation plan #{plan.id}",
    )
    return _plan_to_detail_out(plan, timeline)


@router.post("/remediation-plans/{plan_id}/cancel", response_model=RemediationPlanDetailOut)
def cancel_remediation_plan(
    plan_id: int,
    request: Request,
    service: RemediationService = Depends(get_remediation_service),
    event_service: SecurityEventService = Depends(get_security_event_service),
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR)),
) -> RemediationPlanDetailOut:
    """Cancel a proposed or approved remediation plan."""
    client_ip = get_client_ip(request)
    plan = service.cancel(
        plan_id=plan_id,
        actor_username=principal.username,
        actor_user_id=principal.user.id if principal.user else None,
        actor_role=principal.role,
        client_ip=client_ip,
    )
    timeline = service.list_events_for_plan(plan_id)
    event_service.record(
        event_type=SecurityEventType.REMEDIATION_CANCELLED,
        actor_username=principal.username,
        client_ip=client_ip,
        target=f"{plan.device_id}:{plan.rule_id}:{plan.id}",
        detail=f"Cancelled remediation plan #{plan.id}",
    )
    return _plan_to_detail_out(plan, timeline)
