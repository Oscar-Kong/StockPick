"""Session and lineage state machines for Factor Discovery mining."""
from __future__ import annotations

from services.factor_discovery.mining.errors import MiningSessionStateError
from services.factor_discovery.mining.models import LineageStatus, MiningSessionStatus

TERMINAL_SESSION_STATES = frozenset(
    {
        MiningSessionStatus.BUDGET_EXHAUSTED,
        MiningSessionStatus.COMPLETED,
        MiningSessionStatus.CANCELLED,
        MiningSessionStatus.FAILED,
    }
)

LEGAL_SESSION_TRANSITIONS: dict[MiningSessionStatus, frozenset[MiningSessionStatus]] = {
    MiningSessionStatus.DRAFT: frozenset({MiningSessionStatus.AWAITING_AUTHORIZATION}),
    MiningSessionStatus.AWAITING_AUTHORIZATION: frozenset({MiningSessionStatus.AUTHORIZED, MiningSessionStatus.CANCELLED}),
    MiningSessionStatus.AUTHORIZED: frozenset(
        {MiningSessionStatus.GENERATING_HYPOTHESES, MiningSessionStatus.CANCELLED, MiningSessionStatus.FAILED}
    ),
    MiningSessionStatus.GENERATING_HYPOTHESES: frozenset(
        {
            MiningSessionStatus.AWAITING_HYPOTHESIS_REVIEW,
            MiningSessionStatus.TRANSLATING_FORMULAS,
            MiningSessionStatus.PAUSED,
            MiningSessionStatus.BUDGET_EXHAUSTED,
            MiningSessionStatus.FAILED,
        }
    ),
    MiningSessionStatus.AWAITING_HYPOTHESIS_REVIEW: frozenset(
        {
            MiningSessionStatus.TRANSLATING_FORMULAS,
            MiningSessionStatus.GENERATING_HYPOTHESES,
            MiningSessionStatus.PAUSED,
            MiningSessionStatus.CANCELLED,
        }
    ),
    MiningSessionStatus.TRANSLATING_FORMULAS: frozenset(
        {
            MiningSessionStatus.AWAITING_FORMULA_REVIEW,
            MiningSessionStatus.READY_TO_LAUNCH,
            MiningSessionStatus.PAUSED,
            MiningSessionStatus.BUDGET_EXHAUSTED,
            MiningSessionStatus.FAILED,
        }
    ),
    MiningSessionStatus.AWAITING_FORMULA_REVIEW: frozenset(
        {
            MiningSessionStatus.READY_TO_LAUNCH,
            MiningSessionStatus.TRANSLATING_FORMULAS,
            MiningSessionStatus.PAUSED,
            MiningSessionStatus.CANCELLED,
        }
    ),
    MiningSessionStatus.READY_TO_LAUNCH: frozenset(
        {
            MiningSessionStatus.RUNNING_EXPERIMENTS,
            MiningSessionStatus.PAUSED,
            MiningSessionStatus.CANCELLED,
        }
    ),
    MiningSessionStatus.RUNNING_EXPERIMENTS: frozenset(
        {
            MiningSessionStatus.ANALYZING_RESULTS,
            MiningSessionStatus.PAUSED,
            MiningSessionStatus.BUDGET_EXHAUSTED,
            MiningSessionStatus.FAILED,
            MiningSessionStatus.CANCELLED,
        }
    ),
    MiningSessionStatus.ANALYZING_RESULTS: frozenset(
        {
            MiningSessionStatus.CRITIQUING_RESULTS,
            MiningSessionStatus.PREPARING_REVISIONS,
            MiningSessionStatus.AWAITING_REVISION_REVIEW,
            MiningSessionStatus.READY_TO_RELAUNCH,
            MiningSessionStatus.COMPLETED,
            MiningSessionStatus.PAUSED,
            MiningSessionStatus.BUDGET_EXHAUSTED,
        }
    ),
    MiningSessionStatus.CRITIQUING_RESULTS: frozenset(
        {
            MiningSessionStatus.PREPARING_REVISIONS,
            MiningSessionStatus.AWAITING_REVISION_REVIEW,
            MiningSessionStatus.ANALYZING_RESULTS,
            MiningSessionStatus.COMPLETED,
            MiningSessionStatus.PAUSED,
        }
    ),
    MiningSessionStatus.PREPARING_REVISIONS: frozenset(
        {
            MiningSessionStatus.AWAITING_REVISION_REVIEW,
            MiningSessionStatus.READY_TO_RELAUNCH,
            MiningSessionStatus.COMPLETED,
            MiningSessionStatus.PAUSED,
        }
    ),
    MiningSessionStatus.AWAITING_REVISION_REVIEW: frozenset(
        {
            MiningSessionStatus.READY_TO_RELAUNCH,
            MiningSessionStatus.PREPARING_REVISIONS,
            MiningSessionStatus.COMPLETED,
            MiningSessionStatus.PAUSED,
            MiningSessionStatus.CANCELLED,
        }
    ),
    MiningSessionStatus.READY_TO_RELAUNCH: frozenset(
        {
            MiningSessionStatus.RUNNING_EXPERIMENTS,
            MiningSessionStatus.PAUSED,
            MiningSessionStatus.CANCELLED,
        }
    ),
    MiningSessionStatus.PAUSED: frozenset(
        {
            MiningSessionStatus.GENERATING_HYPOTHESES,
            MiningSessionStatus.AWAITING_HYPOTHESIS_REVIEW,
            MiningSessionStatus.TRANSLATING_FORMULAS,
            MiningSessionStatus.AWAITING_FORMULA_REVIEW,
            MiningSessionStatus.READY_TO_LAUNCH,
            MiningSessionStatus.RUNNING_EXPERIMENTS,
            MiningSessionStatus.ANALYZING_RESULTS,
            MiningSessionStatus.CRITIQUING_RESULTS,
            MiningSessionStatus.PREPARING_REVISIONS,
            MiningSessionStatus.AWAITING_REVISION_REVIEW,
            MiningSessionStatus.READY_TO_RELAUNCH,
            MiningSessionStatus.CANCELLED,
            MiningSessionStatus.COMPLETED,
        }
    ),
}


def validate_session_transition(current: MiningSessionStatus, target: MiningSessionStatus) -> None:
    if current in TERMINAL_SESSION_STATES:
        raise MiningSessionStateError("SESSION_TERMINAL", current.value)
    allowed = LEGAL_SESSION_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise MiningSessionStateError("INVALID_SESSION_TRANSITION", f"{current.value}->{target.value}")


def default_pause_policy_for_mode(mode: str) -> list[str]:
    if mode == "supervised":
        return ["BEFORE_EACH_EXPERIMENT", "BEFORE_EACH_REVISION", "EVERY_HYPOTHESIS", "EVERY_FORMULA"]
    if mode == "bounded_auto":
        return ["ONLY_ON_POLICY_TRIGGER", "BEFORE_EACH_REVISION"]
    return ["ONLY_ON_POLICY_TRIGGER"]


def is_lineage_active(status: str) -> bool:
    return status not in {
        LineageStatus.STOPPED.value,
        LineageStatus.HYPOTHESIS_REJECTED.value,
        LineageStatus.FORMULA_REJECTED.value,
        LineageStatus.REVISION_REJECTED.value,
        LineageStatus.PROMISING_FOR_HUMAN_REVIEW.value,
        LineageStatus.COMPLETED_AFTER_SESSION_CANCELLATION.value,
    }
