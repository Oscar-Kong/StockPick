"""Promotion candidate lifecycle transitions with audit trail."""
from __future__ import annotations

from models.schemas_factor_promotion import FactorPromotionStatus

_ALLOWED: dict[FactorPromotionStatus, frozenset[FactorPromotionStatus]] = {
    FactorPromotionStatus.EXPERIMENTAL: frozenset(
        {FactorPromotionStatus.STAGED, FactorPromotionStatus.REJECTED, FactorPromotionStatus.ARCHIVED}
    ),
    FactorPromotionStatus.STAGED: frozenset(
        {
            FactorPromotionStatus.PROMOTION_CANDIDATE,
            FactorPromotionStatus.REJECTED,
            FactorPromotionStatus.ARCHIVED,
        }
    ),
    FactorPromotionStatus.PROMOTION_CANDIDATE: frozenset(
        {FactorPromotionStatus.SHADOW, FactorPromotionStatus.REJECTED, FactorPromotionStatus.ARCHIVED}
    ),
    FactorPromotionStatus.SHADOW: frozenset(
        {
            FactorPromotionStatus.APPROVED_FOR_MANUAL_INTEGRATION,
            FactorPromotionStatus.REJECTED,
            FactorPromotionStatus.ARCHIVED,
        }
    ),
    FactorPromotionStatus.APPROVED_FOR_MANUAL_INTEGRATION: frozenset({FactorPromotionStatus.ARCHIVED}),
    FactorPromotionStatus.REJECTED: frozenset(
        {FactorPromotionStatus.EXPERIMENTAL, FactorPromotionStatus.ARCHIVED}
    ),
    FactorPromotionStatus.ARCHIVED: frozenset(),
}

_APPROVAL_REQUIRES_GATES = {
    FactorPromotionStatus.PROMOTION_CANDIDATE,
    FactorPromotionStatus.SHADOW,
    FactorPromotionStatus.APPROVED_FOR_MANUAL_INTEGRATION,
}


def can_transition(current: FactorPromotionStatus, target: FactorPromotionStatus) -> bool:
    if current == target:
        return True
    return target in _ALLOWED.get(current, frozenset())


def validate_transition(current: FactorPromotionStatus, target: FactorPromotionStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(f"illegal promotion transition: {current.value} -> {target.value}")


def requires_gate_pass(target: FactorPromotionStatus) -> bool:
    return target in _APPROVAL_REQUIRES_GATES
