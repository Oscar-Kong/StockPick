"""Deterministic stopping decisions for mining sessions."""
from __future__ import annotations

from services.factor_discovery.mining.models import (
    FactorMiningBudgetPolicy,
    FactorMiningStoppingPolicy,
    LineageStatus,
    MiningSessionStatus,
    MiningStoppingDecision,
    SessionUsageCounters,
)
from services.factor_discovery.mining.repositories import FactorMiningLineageRepository
from services.factor_discovery.mining.state_machine import is_lineage_active


class MiningStoppingService:
    ORDER = (
        "integrity_failure",
        "human_cancellation",
        "session_budget_exhausted",
        "evaluation_budget_exhausted",
        "exposure_budget_exhausted",
        "revision_round_exhausted",
        "failure_count_exhausted",
        "no_active_lineages",
        "all_candidates_invalid",
        "duplicate_only_round",
        "futility",
        "high_redundancy",
        "promising_reached",
        "all_work_complete",
    )

    def __init__(self) -> None:
        self._lineages = FactorMiningLineageRepository()

    def evaluate(
        self,
        *,
        session_id: str,
        session_status: str,
        stopping_policy: FactorMiningStoppingPolicy,
        budget: FactorMiningBudgetPolicy,
        usage: SessionUsageCounters,
        budget_exhausted: bool = False,
        cancelled: bool = False,
    ) -> MiningStoppingDecision:
        lineages = self._lineages.list_for_session(session_id)
        active = [l for l in lineages if is_lineage_active(l.status)]
        promising = [l for l in lineages if l.status == LineageStatus.PROMISING_FOR_HUMAN_REVIEW.value]
        stopped = [l for l in lineages if l.status == LineageStatus.STOPPED.value]

        if cancelled:
            return MiningStoppingDecision(
                should_stop=True,
                session_terminal_status=MiningSessionStatus.CANCELLED,
                reason_codes=["human_cancellation"],
            )
        if budget_exhausted and stopping_policy.stop_on_budget_exhausted:
            return MiningStoppingDecision(
                should_stop=True,
                session_terminal_status=MiningSessionStatus.BUDGET_EXHAUSTED,
                reason_codes=["session_budget_exhausted"],
            )
        if usage.formulas_evaluated >= budget.max_formulas_reaching_evaluation:
            return MiningStoppingDecision(
                should_stop=True,
                session_terminal_status=MiningSessionStatus.BUDGET_EXHAUSTED,
                reason_codes=["evaluation_budget_exhausted"],
            )
        if usage.validation_exposures >= budget.max_validation_exposures_per_lineage * max(len(lineages), 1):
            return MiningStoppingDecision(
                should_pause=True,
                reason_codes=["exposure_budget_exhausted"],
                recommended_human_action="authorize_new_session_for_validation_informed_revisions",
            )
        if promising and stopping_policy.stop_on_all_lineages_rejected:
            return MiningStoppingDecision(
                should_pause=True,
                affected_lineages=[l.lineage_id for l in promising],
                reason_codes=["promising_reached"],
                recommended_human_action="review_promising_candidates",
            )
        if lineages and not active:
            return MiningStoppingDecision(
                should_stop=True,
                session_terminal_status=MiningSessionStatus.COMPLETED,
                affected_lineages=[l.lineage_id for l in stopped],
                reason_codes=["all_work_complete"],
            )
        if stopping_policy.stop_on_all_lineages_rejected and lineages and not active:
            return MiningStoppingDecision(
                should_stop=True,
                session_terminal_status=MiningSessionStatus.COMPLETED,
                reason_codes=["no_active_lineages"],
            )
        return MiningStoppingDecision(should_stop=False)

    def should_stop_session(
        self,
        *,
        session_id: str,
        stopping_policy: FactorMiningStoppingPolicy,
        usage: SessionUsageCounters,
        budget_exhausted: bool,
    ) -> tuple[bool, str | None]:
        decision = self.evaluate(
            session_id=session_id,
            session_status="",
            stopping_policy=stopping_policy,
            budget=FactorMiningBudgetPolicy(),
            usage=usage,
            budget_exhausted=budget_exhausted,
        )
        if decision.should_stop:
            return True, decision.reason_codes[0] if decision.reason_codes else "all_work_complete"
        return False, None

    def terminal_status(self, reason: str) -> MiningSessionStatus:
        if reason == "budget_exhausted" or reason == "session_budget_exhausted":
            return MiningSessionStatus.BUDGET_EXHAUSTED
        if reason == "human_cancellation":
            return MiningSessionStatus.CANCELLED
        return MiningSessionStatus.COMPLETED
