"""Critique orchestration with validation-exposure controls."""
from __future__ import annotations

from services.factor_discovery.llm.interpretation_service import FactorRunInterpretationService
from services.factor_discovery.mining.exposure_service import MiningExposureService
from services.factor_discovery.mining.models import ContextTier, CritiqueRevisionRecommendation, FactorMiningBudgetPolicy


class MiningCritiqueOrchestrator:
    def __init__(self, *, llm_client=None) -> None:
        self._interpret = FactorRunInterpretationService(llm_client=llm_client)
        self._exposure = MiningExposureService()

    def run_critique(
        self,
        *,
        session_id: str,
        lineage_id: str,
        formula_hash: str | None,
        run_id: str,
        budget: FactorMiningBudgetPolicy,
        actor: str,
        context_tier: ContextTier = ContextTier.DISCOVERY_PLUS_VALIDATION_SUMMARY,
    ) -> dict:
        self._exposure.check_exposure(
            session_id=session_id,
            lineage_id=lineage_id,
            formula_hash=formula_hash,
            budget=budget,
            context_tier=context_tier,
        )
        existing = self._exposure.find_existing(
            session_id=session_id,
            run_id=run_id,
            operation_type="RUN_CRITIQUE",
            context_tier=context_tier,
        )
        if existing:
            return {"interaction_id": existing.get("llm_interaction_id"), "idempotent": True}
        reservation = self._exposure.reserve(
            session_id=session_id,
            lineage_id=lineage_id,
            formula_hash=formula_hash,
            operation_type="RUN_CRITIQUE",
            context_tier=context_tier,
        )
        try:
            out = self._interpret.interpret(run_id, actor=actor, include_opened_sealed=False)
            self._exposure.finalize(reservation, llm_interaction_id=out.get("interaction_id"), artifact_id=None)
            recommendation = CritiqueRevisionRecommendation.RECOMMENDED.value
            return {**out, "revision_recommendation": recommendation}
        except Exception as exc:
            self._exposure.finalize(reservation, llm_interaction_id=None, artifact_id=None, failed=True)
            raise exc
