"""Factor Discovery research validation orchestrator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from engines.factor.discovery.acceptance import evaluate_acceptance_gate
from engines.factor.discovery.compiler import CompiledFactorPlan
from engines.factor.discovery.metrics_adapter import evaluate_cross_sectional_metrics
from engines.factor.discovery.outcomes import build_factor_outcomes
from engines.factor.discovery.panel_models import FactorExecutionResult, FactorInputPanel
from engines.factor.discovery.periods import mask_for_sessions, resolve_research_periods
from engines.factor.discovery.portfolio_validation import simulate_long_only_portfolio
from engines.factor.discovery.quantiles import evaluate_quantiles
from engines.factor.discovery.robustness import evaluate_robustness
from engines.factor.discovery.sealed_test import (
    build_sealed_test_status,
    sealed_test_receipt_hash,
    validate_sealed_test_access,
)
from engines.factor.discovery.result_hashing import hash_panel_content
from engines.factor.discovery.sessions import align_panel_to_canonical_sessions
from engines.factor.discovery.session_hashing import canonical_session_hash
from engines.factor.discovery.validation_errors import HashMismatchError
from engines.factor.discovery.validation_hashing import validation_artifact_hash, validation_config_hash
from engines.factor.discovery.validation_models import (
    VALIDATION_ENGINE_VERSION,
    FactorValidationArtifact,
    FactorValidationConfig,
    SealedTestAccess,
)
from engines.factor.discovery.statistics import benjamini_hochberg, bonferroni_correction
from engines.factor.discovery.walk_forward import run_walk_forward_validation
from models.schemas_factor_discovery import DiscoveryPeriodSplit, FactorDirection


@dataclass(frozen=True)
class BenchmarkFactorPanel:
    """Optional externally supplied benchmark factor scores (same index, PIT policy)."""

    scores: dict[str, pd.Series]
    provenance_note: str = "externally_supplied"


def _verify_hashes(
    plan: CompiledFactorPlan,
    execution_result: FactorExecutionResult,
    input_panel: FactorInputPanel,
) -> None:
    if execution_result.formula_hash_value != plan.formula_hash_value:
        raise HashMismatchError(code="formula_hash", message="execution formula hash mismatch")
    if execution_result.plan_hash_value != plan.plan_hash_value:
        raise HashMismatchError(code="plan_hash", message="execution plan hash mismatch")
    if execution_result.panel_content_hash != input_panel.content_hash:
        raise HashMismatchError(code="panel_hash", message="execution panel hash mismatch")
    if not execution_result.factor_values.index.equals(input_panel.frame.index):
        raise HashMismatchError(code="index_mismatch", message="execution output index mismatch")


def _direction_str(direction: FactorDirection | str) -> str:
    if isinstance(direction, FactorDirection):
        return direction.value
    return str(direction)


def _evaluate_redundancy(
    scores: pd.Series,
    benchmarks: BenchmarkFactorPanel | None,
    *,
    period_mask: pd.Series,
) -> dict[str, Any]:
    if benchmarks is None or not benchmarks.scores:
        return {"available": False, "reason": "no_benchmark_factors"}
    corrs: list[float] = []
    for name, bench in benchmarks.scores.items():
        aligned = bench.reindex(scores.index)
        df = pd.DataFrame({"s": scores, "b": aligned})[period_mask.reindex(scores.index, fill_value=False)]
        df = df.dropna()
        if len(df) < 5:
            continue
        for _, grp in df.groupby(level=0):
            if len(grp) < 5:
                continue
            c = grp["s"].corr(grp["b"], method="spearman")
            if c is not None and np.isfinite(c):
                corrs.append(abs(float(c)))
    if not corrs:
        return {"available": False, "reason": "insufficient_overlap"}
    return {
        "available": True,
        "mean_abs_correlation": round(float(np.mean(corrs)), 4),
        "max_benchmark_correlation": round(float(max(corrs)), 4),
        "benchmark_count": len(benchmarks.scores),
    }


def _multiple_testing(
    validation_metrics: dict[str, Any],
    config: FactorValidationConfig,
) -> dict[str, Any]:
    p_naive = validation_metrics.get("rank_ic_p_value")
    p_primary = validation_metrics.get("rank_ic_p_value_primary")
    p_for_correction = p_primary if p_primary is not None else p_naive
    if p_for_correction is None:
        return {"available": False, "reason": "no_p_value"}
    family = config.declared_hypothesis_family_size
    if family is None:
        return {
            "available": False,
            "reason": "family_size_unknown",
            "raw_p_value": p_naive,
            "primary_p_value": p_primary,
            "corrected_significance": "UNAVAILABLE",
        }
    if config.multiple_testing_method == "bonferroni":
        passed = bonferroni_correction([p_for_correction], family, config.significance_level)[0]
    elif config.multiple_testing_method == "benjamini_hochberg":
        passed = benjamini_hochberg([p_for_correction], config.significance_level)[0]
    else:
        passed = p_for_correction <= config.significance_level
    return {
        "available": True,
        "method": config.multiple_testing_method,
        "family_size": family,
        "raw_p_value": p_naive,
        "primary_p_value": p_primary,
        "p_value_used_for_correction": p_for_correction,
        "significant_after_correction": passed,
        "uses_robust_primary_p_value": p_primary is not None,
    }


def validate_factor_execution(
    *,
    plan: CompiledFactorPlan,
    execution_result: FactorExecutionResult,
    input_panel: FactorInputPanel,
    period_split: DiscoveryPeriodSplit,
    validation_config: FactorValidationConfig,
    factor_direction: FactorDirection | str = FactorDirection.HIGHER_IS_BETTER,
    sealed_test_access: SealedTestAccess | None = None,
    benchmark_factors: BenchmarkFactorPanel | None = None,
    factor_id: str | None = None,
    factor_version: str | None = None,
) -> FactorValidationArtifact:
    """Validate an executed factor against forward outcomes and research gates."""
    aligned_panel, calendar, missing_rows = align_panel_to_canonical_sessions(input_panel)
    session_hash = canonical_session_hash(calendar)
    if execution_result.formula_hash_value != plan.formula_hash_value:
        raise HashMismatchError(code="formula_hash", message="execution formula hash mismatch")
    if execution_result.plan_hash_value != plan.plan_hash_value:
        raise HashMismatchError(code="plan_hash", message="execution plan hash mismatch")
    aligned_panel_hash = hash_panel_content(
        aligned_panel.frame,
        eligibility=aligned_panel.eligibility,
        data_source_policy_id=aligned_panel.data_source_policy_id,
        provider_id=aligned_panel.provider_id,
        prices_adjusted=aligned_panel.prices_adjusted,
        field_provenance=aligned_panel.field_provenance,
        panel_version=aligned_panel.panel_version,
        canonical_session_hash_value=session_hash,
    )
    if execution_result.panel_content_hash not in {input_panel.content_hash, aligned_panel_hash, aligned_panel.content_hash}:
        raise HashMismatchError(code="panel_hash", message="execution panel hash mismatch")
    if not execution_result.factor_values.index.equals(aligned_panel.frame.index):
        raise HashMismatchError(code="index_mismatch", message="execution output index mismatch")

    direction = _direction_str(factor_direction)
    cfg_hash = validation_config_hash(validation_config)
    periods = resolve_research_periods(
        period_split,
        calendar,
        config=validation_config,
        canonical_session_hash_value=session_hash,
    )

    scores = execution_result.factor_values
    outcome_hashes: dict[str, str] = {}
    outcomes_by_horizon: dict[int, Any] = {}
    for h in validation_config.outcome_horizons_sessions:
        op = build_factor_outcomes(
            aligned_panel,
            horizon_sessions=h,
            config=validation_config,
            calendar=calendar,
            canonical_session_hash_value=session_hash,
        )
        outcomes_by_horizon[h] = op
        outcome_hashes[str(h)] = op.panel_hash

    primary = validation_config.primary_horizon_sessions
    if primary not in outcomes_by_horizon:
        raise ValueError(f"primary_horizon_sessions {primary} not in outcome_horizons_sessions")
    primary_outcome = outcomes_by_horizon[primary]

    disc_mask = mask_for_sessions(scores.index, periods.discovery_sessions)
    val_mask = mask_for_sessions(scores.index, periods.validation_sessions)
    sealed_mask = mask_for_sessions(scores.index, periods.sealed_test_sessions)

    discovery_metrics = evaluate_cross_sectional_metrics(
        scores, primary_outcome, period_mask=disc_mask, config=validation_config, direction=direction
    )
    validation_metrics = evaluate_cross_sectional_metrics(
        scores, primary_outcome, period_mask=val_mask, config=validation_config, direction=direction
    )

    quantile_results = evaluate_quantiles(
        scores, primary_outcome, period_mask=val_mask, config=validation_config, direction=direction
    )
    portfolio_results = simulate_long_only_portfolio(
        scores,
        primary_outcome,
        sessions=periods.validation_sessions,
        config=validation_config,
        direction=direction,
    )
    walk_forward = run_walk_forward_validation(
        scores,
        primary_outcome,
        discovery_sessions=periods.discovery_sessions,
        validation_sessions=periods.validation_sessions,
        config=validation_config,
        direction=direction,
    )
    robustness = evaluate_robustness(
        scores,
        primary_outcome,
        aligned_panel.frame,
        period_mask=val_mask,
        config=validation_config,
        direction=direction,
    )
    redundancy = _evaluate_redundancy(scores, benchmark_factors, period_mask=val_mask)
    multiple_testing = _multiple_testing(validation_metrics, validation_config)

    sealed_metrics: dict[str, Any] | None = None
    receipt: str | None = None
    opened = False
    if sealed_test_access is not None:
        validate_sealed_test_access(
            sealed_test_access,
            formula_hash=plan.formula_hash_value,
            plan_hash=plan.plan_hash_value,
        )
        opened = True
        sealed_metrics = evaluate_cross_sectional_metrics(
            scores, primary_outcome, period_mask=sealed_mask, config=validation_config, direction=direction
        )
        receipt = sealed_test_receipt_hash(
            formula_hash=plan.formula_hash_value,
            plan_hash=plan.plan_hash_value,
            validation_config_hash=cfg_hash,
            period_resolution_hash=periods.period_resolution_hash,
            sealed_result_hash=str(hash(str(sealed_metrics))),
            access=sealed_test_access,
        )

    sealed_status = build_sealed_test_status(
        sessions=periods.sealed_test_sessions,
        opened=opened,
        receipt_hash=receipt,
    )

    acceptance = evaluate_acceptance_gate(
        config=validation_config,
        validation_metrics=validation_metrics,
        discovery_metrics=discovery_metrics,
        quantile_results=quantile_results,
        portfolio_results=portfolio_results,
        walk_forward=walk_forward,
        robustness=robustness,
        redundancy=redundancy,
        multiple_testing=multiple_testing,
        sealed_status=sealed_status.status,
    )

    limitations = [
        "missing delisting returns not imputed with zero",
        "descriptive naive t-statistics retained for transparency only",
    ]
    if validation_config.declared_hypothesis_family_size is None:
        limitations.append("multiple-testing family size not declared")
    if primary > 1:
        limitations.append(f"overlapping outcomes for horizon {primary} sessions")

    warnings = list(periods.warnings)
    if missing_rows > 0:
        warnings.append(f"canonical session alignment added {missing_rows} missing rows")

    artifact_hash = validation_artifact_hash(
        formula_hash=plan.formula_hash_value,
        plan_hash=plan.plan_hash_value,
        execution_hash=execution_result.execution_hash_value,
        outcome_hashes=outcome_hashes,
        period_resolution_hash=periods.period_resolution_hash,
        validation_config_hash_value=cfg_hash,
        sealed_opened=opened,
        sealed_access=sealed_test_access,
    )

    return FactorValidationArtifact(
        factor_id=factor_id,
        factor_version=factor_version,
        formula_hash=plan.formula_hash_value,
        plan_hash=plan.plan_hash_value,
        panel_hash=aligned_panel_hash,
        canonical_session_hash=session_hash,
        execution_hash=execution_result.execution_hash_value,
        validation_config_hash=cfg_hash,
        period_resolution_hash=periods.period_resolution_hash,
        validation_artifact_hash=artifact_hash,
        factor_direction=direction,
        primary_horizon_sessions=primary,
        discovery_metrics=discovery_metrics,
        validation_metrics=validation_metrics,
        sealed_test=sealed_status,
        sealed_test_metrics=sealed_metrics,
        walk_forward=walk_forward,
        robustness=robustness,
        quantile_results=quantile_results,
        portfolio_results=portfolio_results,
        statistical_results={
            "rank_ic_t_stat": validation_metrics.get("rank_ic_t_stat"),
            "rank_ic_p_value": validation_metrics.get("rank_ic_p_value"),
            "rank_ic_p_value_primary": validation_metrics.get("rank_ic_p_value_primary"),
            "rank_ic_t_stat_primary": validation_metrics.get("rank_ic_t_stat_primary"),
            "rank_ic_significance": validation_metrics.get("rank_ic_significance"),
            "rank_ic_ci_95": validation_metrics.get("rank_ic_ci_95"),
        },
        multiple_testing=multiple_testing,
        redundancy=redundancy,
        acceptance_gate=acceptance,
        outcome_panel_hashes=outcome_hashes,
        diagnostics={
            "missing_session_rows": missing_rows,
            "calendar_sessions": len(calendar.sessions),
        },
        warnings=warnings,
        limitations=limitations,
        determinism_metadata={
            "validation_engine_version": VALIDATION_ENGINE_VERSION,
            "execution_timing": validation_config.execution_timing,
            "canonical_session_hash": session_hash,
            "primary_significance_method": validation_config.primary_significance_method,
        },
    )
