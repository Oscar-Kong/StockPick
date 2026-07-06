"""Deterministic critique categories for closed mining runs."""
from __future__ import annotations

from engines.factor.discovery.validation_models import FactorValidationArtifact
from services.factor_discovery.mining.models import ContextTier, FailureCategory


_RULE_CATEGORY_MAP: dict[str, FailureCategory] = {
    "predictive_ic": FailureCategory.WEAK_RANK_IC,
    "ic_stability": FailureCategory.UNSTABLE_IC,
    "coverage": FailureCategory.DATA_COVERAGE,
    "quantile_monotonicity": FailureCategory.POOR_QUANTILE_MONOTONICITY,
    "turnover": FailureCategory.HIGH_TURNOVER,
    "cost": FailureCategory.COST_EROSION,
    "drawdown": FailureCategory.HIGH_DRAWDOWN,
    "walk_forward": FailureCategory.WALK_FORWARD_INSTABILITY,
    "robustness": FailureCategory.REGIME_DEPENDENCE,
    "redundancy": FailureCategory.REDUNDANCY,
    "multiple_testing": FailureCategory.MULTIPLE_TESTING_FAILURE,
    "significance": FailureCategory.INSUFFICIENT_SIGNIFICANCE,
}


def derive_failure_categories(artifact: FactorValidationArtifact) -> list[FailureCategory]:
    """Map acceptance-gate failures to closed critique categories."""
    active: list[FailureCategory] = []
    seen: set[FailureCategory] = set()
    for rule in artifact.acceptance_gate.rules:
        if rule.status != "FAIL":
            continue
        category = _RULE_CATEGORY_MAP.get(rule.category, FailureCategory.INCONCLUSIVE_EVIDENCE)
        if category not in seen:
            seen.add(category)
            active.append(category)
    if not active and artifact.acceptance_gate.overall_status in {"FAIL", "INCONCLUSIVE"}:
        active.append(FailureCategory.INCONCLUSIVE_EVIDENCE)
    turnover = artifact.portfolio_results.get("annualized_turnover")
    if turnover is not None and turnover > 2.0 and FailureCategory.HIGH_TURNOVER not in seen:
        active.append(FailureCategory.HIGH_TURNOVER)
    redundancy = artifact.redundancy.get("max_benchmark_correlation")
    if redundancy is not None and redundancy > 0.85 and FailureCategory.REDUNDANCY not in seen:
        active.append(FailureCategory.REDUNDANCY)
    return active


def artifact_context_tier(context_tier: ContextTier, artifact: FactorValidationArtifact) -> dict:
    """Build LLM-safe evidence payload without sealed metrics."""
    if context_tier == ContextTier.DISCOVERY_ONLY:
        return {
            "discovery_metrics": artifact.discovery_metrics,
            "limitations": artifact.limitations,
            "warnings": artifact.warnings,
        }
    if context_tier == ContextTier.DISCOVERY_PLUS_VALIDATION_SUMMARY:
        return {
            "discovery_metrics": artifact.discovery_metrics,
            "validation_summary": {
                "mean_rank_ic": artifact.validation_metrics.get("mean_rank_ic"),
                "rank_ic_ir": artifact.validation_metrics.get("rank_ic_ir"),
                "valid_date_count": artifact.validation_metrics.get("valid_date_count"),
            },
            "acceptance_gate": artifact.acceptance_gate.model_dump(mode="json"),
            "failure_categories": [c.value for c in derive_failure_categories(artifact)],
            "limitations": artifact.limitations,
            "warnings": artifact.warnings,
        }
    return {
        "discovery_metrics": artifact.discovery_metrics,
        "validation_metrics": artifact.validation_metrics,
        "walk_forward": artifact.walk_forward,
        "portfolio_results": artifact.portfolio_results,
        "robustness": artifact.robustness,
        "multiple_testing": artifact.multiple_testing,
        "acceptance_gate": artifact.acceptance_gate.model_dump(mode="json"),
        "failure_categories": [c.value for c in derive_failure_categories(artifact)],
        "limitations": artifact.limitations,
        "warnings": artifact.warnings,
    }
