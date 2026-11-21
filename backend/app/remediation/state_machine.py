"""Remediation plan state machine and transition rules."""

from __future__ import annotations

from app.domain.entities.remediation import PlanStatus
from app.domain.errors import InvalidTransitionError

VALID_TRANSITIONS: dict[PlanStatus, frozenset[PlanStatus]] = {
    PlanStatus.PROPOSED: frozenset({
        PlanStatus.APPROVED,
        PlanStatus.REJECTED,
        PlanStatus.CANCELLED,
        PlanStatus.EXPIRED,
    }),
    PlanStatus.APPROVED: frozenset({
        PlanStatus.CANCELLED,
        PlanStatus.EXPIRED,
    }),
    PlanStatus.REJECTED: frozenset(),
    PlanStatus.CANCELLED: frozenset(),
    PlanStatus.EXPIRED: frozenset(),
    # Reserved statuses for Remediation D have no inbound/outbound transitions in Phase C
    PlanStatus.APPLYING: frozenset(),
    PlanStatus.APPLIED: frozenset(),
    PlanStatus.VERIFIED: frozenset(),
    PlanStatus.VERIFY_FAILED: frozenset(),
    PlanStatus.FAILED: frozenset(),
    PlanStatus.ROLLED_BACK: frozenset(),
}

FINAL_STATUSES: frozenset[PlanStatus] = frozenset({
    PlanStatus.REJECTED,
    PlanStatus.CANCELLED,
    PlanStatus.EXPIRED,
})


def is_valid_transition(current: PlanStatus, target: PlanStatus) -> bool:
    """Return True if transition from current to target is allowed."""
    return target in VALID_TRANSITIONS.get(current, frozenset())


def validate_transition(current: PlanStatus, target: PlanStatus) -> None:
    """Validate transition from current to target.

    Raises InvalidTransitionError if transition is not permitted.
    """
    if not is_valid_transition(current, target):
        raise InvalidTransitionError(
            f"Invalid transition from {current.value} to {target.value}"
        )
