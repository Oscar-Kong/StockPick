"""Deterministic post-validation decision engine for mining lineages."""
from __future__ import annotations

from engines.factor.discovery.validation_models import FactorValidationArtifact
from services.factor_discovery.mining.critique_step import derive_failure_categories
from services.factor_discovery.mining.futility_policy import assess_lineage_futility
from services.factor_discovery.mining.models import (
    FailureCategory,
    FactorMiningBudgetPolicy,
    MiningPostValidationDecision,
    PostValidationAction,
)
from services.factor_discovery.mining.promising_policy import PromisingCandidatePolicy, evaluate_promising


def decide_post_validation(
    *,
    lineage_id: str,
    evaluation_id: str,
    artifact: FactorValidationArtifact,
    artifact_integrity_ok: bool,
    revision_depth: int,
    budget: FactorMiningBudgetPolicy,
    usage_formulas_evaluated: int,
    exposure_available: bool,
    session_cancelled: bool = False,
    promising_policy: PromisingCandidatePolicy | None = None,
) -> MiningPostValidationDecision:
    categories = derive_failure_categories(artifact)
    promising = evaluate_promising(artifact, policy=promising_policy, integrity_ok=artifact_integrity_ok)
    robust_ok = bool(artifact.statistical_results.get("robust_significant"))
    mt_ok = artifact.acceptance_gate.overall_status != "FAIL" or not any(
        c == FailureCategory.MULTIPLE_TESTING_FAILURE for c in categories
    )
    revision_remaining = max(0, budget.max_revision_rounds_per_lineage - revision_depth)
    eval_remaining = max(0, budget.max_formulas_reaching_evaluation - usage_formulas_evaluated)
    redundancy_high = FailureCategory.REDUNDANCY in categories

    if session_cancelled:
        return MiningPostValidationDecision(
            lineage_id=lineage_id,
            evaluation_id=evaluation_id,
            artifact_id=None,
            acceptance_status=artifact.acceptance_gate.overall_status,
            failure_categories=categories,
            integrity_ok=artifact_integrity_ok,
            recommended_action=PostValidationAction.STOP_LINEAGE,
            reason_codes=["SESSION_CANCELLED"],
        )

    if not artifact_integrity_ok:
        return MiningPostValidationDecision(
            lineage_id=lineage_id,
            evaluation_id=evaluation_id,
            artifact_id=artifact.validation_artifact_hash,
            acceptance_status=artifact.acceptance_gate.overall_status,
            failure_categories=categories,
            integrity_ok=False,
            recommended_action=PostValidationAction.STOP_LINEAGE,
            reason_codes=["INTEGRITY_FAILURE"],
        )

    if promising.overall == "PROMISING_FOR_HUMAN_REVIEW":
        return MiningPostValidationDecision(
            lineage_id=lineage_id,
            evaluation_id=evaluation_id,
            artifact_id=artifact.validation_artifact_hash,
            acceptance_status=artifact.acceptance_gate.overall_status,
            failure_categories=categories,
            integrity_ok=True,
            robust_significance_ok=robust_ok,
            multiple_testing_ok=mt_ok,
            exposure_available=exposure_available,
            promising_result=promising,
            recommended_action=PostValidationAction.PAUSE_PROMISING,
            reason_codes=["PROMISING_POLICY_PASS"],
        )

    futility = assess_lineage_futility(
        evaluations_count=revision_depth + 1,
        artifact=artifact,
        categories=categories,
        revision_remaining=revision_remaining,
    )
    if futility.is_futile:
        return MiningPostValidationDecision(
            lineage_id=lineage_id,
            evaluation_id=evaluation_id,
            artifact_id=artifact.validation_artifact_hash,
            acceptance_status=artifact.acceptance_gate.overall_status,
            failure_categories=categories,
            integrity_ok=True,
            revision_eligible=False,
            revision_rounds_remaining=revision_remaining,
            recommended_action=PostValidationAction.STOP_LINEAGE,
            reason_codes=futility.reason_codes,
        )

    if categories and revision_remaining > 0 and exposure_available and eval_remaining > 0:
        return MiningPostValidationDecision(
            lineage_id=lineage_id,
            evaluation_id=evaluation_id,
            artifact_id=artifact.validation_artifact_hash,
            acceptance_status=artifact.acceptance_gate.overall_status,
            failure_categories=categories,
            integrity_ok=True,
            robust_significance_ok=robust_ok,
            multiple_testing_ok=mt_ok,
            exposure_available=exposure_available,
            revision_eligible=True,
            revision_rounds_remaining=revision_remaining,
            evaluation_budget_remaining=eval_remaining,
            redundancy_high=redundancy_high,
            promising_result=promising,
            recommended_action=PostValidationAction.REQUEST_CRITIQUE,
            reason_codes=["RESEARCH_FAILURE_CATEGORIES_ACTIVE"],
        )

    if categories and revision_remaining > 0 and not exposure_available:
        return MiningPostValidationDecision(
            lineage_id=lineage_id,
            evaluation_id=evaluation_id,
            artifact_id=artifact.validation_artifact_hash,
            acceptance_status=artifact.acceptance_gate.overall_status,
            failure_categories=categories,
            integrity_ok=True,
            exposure_available=False,
            revision_eligible=False,
            recommended_action=PostValidationAction.AWAIT_HUMAN_DECISION,
            reason_codes=["EXPOSURE_BUDGET_EXHAUSTED"],
        )

    return MiningPostValidationDecision(
        lineage_id=lineage_id,
        evaluation_id=evaluation_id,
        artifact_id=artifact.validation_artifact_hash,
        acceptance_status=artifact.acceptance_gate.overall_status,
        failure_categories=categories,
        integrity_ok=True,
        promising_result=promising,
        recommended_action=PostValidationAction.STOP_LINEAGE,
        reason_codes=["NO_REVISION_PATH"],
    )
