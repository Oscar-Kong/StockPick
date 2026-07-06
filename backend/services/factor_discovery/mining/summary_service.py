"""Deterministic session summary for mining loops."""
from __future__ import annotations

from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit
from services.factor_discovery.mining.budget_service import load_usage
from services.factor_discovery.mining.hashing import event_log_hash
from services.factor_discovery.mining.models import FactorMiningSessionSummary, LineageStatus
from services.factor_discovery.mining.repositories import (
    FactorMiningEvaluationRepository,
    FactorMiningEventRepository,
    FactorMiningLineageRepository,
    FactorMiningSessionRepository,
)
from services.factor_discovery.multiple_testing_service import derive_family_size
from services.factor_discovery.repositories import FactorAttemptLedgerRepository
from services.research_json import json_dumps, json_loads


class FactorMiningSummaryService:
    def __init__(self) -> None:
        self._sessions = FactorMiningSessionRepository()
        self._events = FactorMiningEventRepository()
        self._lineages = FactorMiningLineageRepository()
        self._evaluations = FactorMiningEvaluationRepository()
        self._attempts = FactorAttemptLedgerRepository()

    def build_summary(self, session_id: str) -> FactorMiningSessionSummary:
        row = self._sessions.get(session_id)
        if row is None:
            raise ValueError(session_id)
        usage = load_usage(row.usage_json)
        lineages = self._lineages.list_for_session(session_id)
        evaluations = self._evaluations.list_for_session(session_id)
        events = self._events.list_for_session(session_id)
        attempts = self._attempts.list_for_family(row.research_family_id)
        vconfig = FactorValidationConfig.model_validate(json_loads(row.validation_config_json, {}))
        family = derive_family_size(
            attempts,
            primary_horizon_sessions=row.primary_horizon_sessions,
            validation_config_family_id="default_v1",
        )
        promising = sum(1 for l in lineages if l.status == LineageStatus.PROMISING_FOR_HUMAN_REVIEW.value)
        stopped = sum(1 for l in lineages if l.status == LineageStatus.STOPPED.value)
        duplicates = sum(1 for e in evaluations if e.is_duplicate)
        summary = FactorMiningSessionSummary(
            session_id=session_id,
            research_objective=row.research_objective,
            research_family_id=row.research_family_id,
            mode=row.session_mode,
            status=row.status,
            budget_used=usage,
            hypotheses_generated=usage.hypotheses_generated,
            formulas_generated=usage.formulas_generated,
            exact_duplicates=duplicates,
            experiments_launched=sum(1 for e in evaluations if e.run_id),
            statistical_hypotheses_evaluated=usage.formulas_evaluated,
            validation_exposures=usage.validation_exposures,
            revision_rounds=usage.revision_rounds,
            lineages_stopped=stopped,
            promising_candidates=promising,
            multiple_testing_family_size=family.effective_family_size,
            session_hash=row.session_config_hash,
            event_log_hash=event_log_hash(
                [
                    {
                        "event_type": e.event_type,
                        "previous_state": e.previous_state,
                        "new_state": e.new_state,
                        "reason_code": e.reason_code,
                        "lineage_id": e.lineage_id,
                        "candidate_id": e.candidate_id,
                        "run_id": e.run_id,
                    }
                    for e in events
                ]
            ),
        )
        self._sessions.update_summary(
            session_id,
            summary_json=json_dumps(summary.model_dump(mode="json")),
            summary_hash=summary.event_log_hash,
        )
        return summary
