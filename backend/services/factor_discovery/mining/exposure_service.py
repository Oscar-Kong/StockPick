"""Validation-data exposure ledger for mining sessions."""
from __future__ import annotations

import uuid

from services.factor_discovery.mining.errors import MiningValidationExposureExceededError
from services.factor_discovery.mining.models import ContextTier, FactorMiningBudgetPolicy
from services.factor_discovery.mining.repositories import FactorMiningExposureRepository


class MiningExposureService:
    def __init__(self) -> None:
        self._repo = FactorMiningExposureRepository()

    def check_exposure(
        self,
        *,
        session_id: str,
        lineage_id: str,
        formula_hash: str | None,
        budget: FactorMiningBudgetPolicy,
        context_tier: ContextTier,
    ) -> None:
        if context_tier == ContextTier.DISCOVERY_ONLY:
            return
        lineage_count = self._repo.count_for_lineage(session_id, lineage_id)
        if lineage_count >= budget.max_validation_exposures_per_lineage:
            raise MiningValidationExposureExceededError(
                "LINEAGE_EXPOSURE_EXCEEDED", f"{lineage_id}:{lineage_count}"
            )
        if formula_hash:
            formula_count = self._repo.count_for_formula(session_id, formula_hash)
            if formula_count >= budget.max_validation_critiques_per_formula:
                raise MiningValidationExposureExceededError(
                    "FORMULA_EXPOSURE_EXCEEDED", f"{formula_hash}:{formula_count}"
                )

    def reserve(
        self,
        *,
        session_id: str,
        lineage_id: str | None,
        formula_hash: str | None,
        operation_type: str,
        context_tier: ContextTier,
        prompt_template_id: str | None = None,
        prompt_template_version: str | None = None,
    ) -> str:
        return self._repo.record(
            session_id=session_id,
            lineage_id=lineage_id,
            formula_hash=formula_hash,
            operation_type=operation_type,
            context_tier=context_tier.value,
            prompt_template_id=prompt_template_id,
            prompt_template_version=prompt_template_version,
            reservation_status="RESERVED",
        )

    def finalize(
        self,
        exposure_id: str,
        *,
        llm_interaction_id: str | None,
        artifact_id: str | None,
        failed: bool = False,
    ) -> None:
        self._repo.update(
            exposure_id,
            llm_interaction_id=llm_interaction_id,
            artifact_id=artifact_id,
            reservation_status="FAILED" if failed else "FINALIZED",
        )

    def record(
        self,
        *,
        session_id: str,
        lineage_id: str | None,
        formula_hash: str | None,
        artifact_id: str | None,
        llm_interaction_id: str | None,
        operation_type: str,
        context_tier: ContextTier,
        prompt_template_version: str | None = None,
    ) -> str:
        return self._repo.record(
            session_id=session_id,
            lineage_id=lineage_id,
            formula_hash=formula_hash,
            artifact_id=artifact_id,
            llm_interaction_id=llm_interaction_id,
            operation_type=operation_type,
            context_tier=context_tier.value,
            prompt_template_version=prompt_template_version,
            reservation_status="FINALIZED",
        )

    def find_existing(
        self,
        *,
        session_id: str,
        run_id: str,
        operation_type: str,
        context_tier: ContextTier,
    ) -> dict | None:
        row = self._repo.find_idempotent(
            session_id=session_id,
            llm_interaction_id=run_id,
            operation_type=operation_type,
            context_tier=context_tier.value,
        )
        if row is None:
            return None
        return {"llm_interaction_id": row.llm_interaction_id, "exposure_id": row.exposure_id}
