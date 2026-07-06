"""Conservative futility stopping for mining lineages."""
from __future__ import annotations

from dataclasses import dataclass

from engines.factor.discovery.validation_models import FactorValidationArtifact
from services.factor_discovery.mining.models import FUTILITY_POLICY_VERSION, FailureCategory


@dataclass(frozen=True)
class FutilityAssessment:
    is_futile: bool
    reason_codes: list[str]
    policy_version: str = FUTILITY_POLICY_VERSION


def assess_lineage_futility(
    *,
    evaluations_count: int,
    artifact: FactorValidationArtifact,
    categories: list[FailureCategory],
    revision_remaining: int,
    min_evaluations: int = 2,
    min_rank_ic_delta: float = 0.01,
) -> FutilityAssessment:
    if evaluations_count < min_evaluations:
        return FutilityAssessment(is_futile=False, reason_codes=[])
    ic = artifact.validation_metrics.get("mean_rank_ic")
    wf = artifact.walk_forward.get("pass_rate")
    robust = artifact.statistical_results.get("robust_significant")
    unsupported = FailureCategory.DATA_COVERAGE in categories and revision_remaining > 0
    if unsupported and revision_remaining == 0:
        return FutilityAssessment(is_futile=True, reason_codes=["UNSUPPORTED_DATA_NO_REVISIONS"])
    if ic is not None and ic < min_rank_ic_delta and not robust and (wf is None or wf < 0.5):
        return FutilityAssessment(is_futile=True, reason_codes=["FUTILITY_NO_IMPROVEMENT"])
    return FutilityAssessment(is_futile=False, reason_codes=[])
