"""Acceptance gate evaluation for Factor Discovery validation."""
from __future__ import annotations

from typing import Any

from engines.factor.discovery.validation_models import (
    AcceptanceGateResult,
    FactorValidationConfig,
    GateRuleResult,
)


def _rule(
    rule_id: str,
    category: str,
    status: str,
    *,
    actual: float | str | None = None,
    threshold: float | str | None = None,
    message: str = "",
) -> GateRuleResult:
    return GateRuleResult(
        rule_id=rule_id,
        category=category,
        status=status,  # type: ignore[arg-type]
        actual=actual,
        threshold=threshold,
        message=message,
    )


def evaluate_acceptance_gate(
    *,
    config: FactorValidationConfig,
    validation_metrics: dict[str, Any],
    discovery_metrics: dict[str, Any],
    quantile_results: dict[str, Any],
    portfolio_results: dict[str, Any],
    walk_forward: dict[str, Any],
    robustness: dict[str, Any],
    redundancy: dict[str, Any],
    multiple_testing: dict[str, Any],
    sealed_status: str,
) -> AcceptanceGateResult:
    rules: list[GateRuleResult] = []
    warnings: list[str] = []

    def _cmp(rule_id: str, cat: str, actual: float | None, threshold: float, op: str) -> GateRuleResult:
        if actual is None:
            return _rule(rule_id, cat, "INCONCLUSIVE", actual=actual, threshold=threshold, message="missing metric")
        ok = actual >= threshold if op == "gte" else actual <= threshold
        return _rule(
            rule_id,
            cat,
            "PASS" if ok else "FAIL",
            actual=round(actual, 6),
            threshold=threshold,
        )

    rules.append(
        _cmp("mean_rank_ic", "predictive_ic", validation_metrics.get("mean_rank_ic"), config.min_mean_rank_ic, "gte")
    )
    rules.append(
        _cmp("rank_ic_ir", "ic_stability", validation_metrics.get("rank_ic_ir"), config.min_rank_ic_ir, "gte")
    )
    rules.append(
        _cmp(
            "positive_rank_ic_pct",
            "ic_stability",
            validation_metrics.get("positive_rank_ic_pct"),
            config.min_positive_ic_pct,
            "gte",
        )
    )
    cov = validation_metrics.get("valid_date_count", 0)
    total = validation_metrics.get("total_dates", 1) or 1
    cov_pct = cov / total
    rules.append(
        _cmp("valid_date_coverage", "coverage", cov_pct, config.min_valid_date_coverage_pct, "gte")
    )
    rules.append(
        _cmp(
            "monotonicity",
            "quantile_monotonicity",
            quantile_results.get("monotonicity_spearman_mean"),
            0.0,
            "gte",
        )
    )
    turnover = portfolio_results.get("mean_turnover_per_rebalance")
    rules.append(
        _cmp("max_turnover", "turnover", turnover, config.max_turnover_per_rebalance, "lte")
    )
    dd = portfolio_results.get("max_drawdown_pct")
    if dd is not None:
        rules.append(_cmp("max_drawdown", "drawdown", abs(dd) / 100.0, config.max_drawdown, "lte"))
    rules.append(
        _cmp(
            "walk_forward_pass_rate",
            "walk_forward",
            walk_forward.get("fold_pass_rate"),
            0.5,
            "gte",
        )
    )
    if config.declared_hypothesis_family_size is None and config.multiple_testing_method != "none":
        rules.append(
            _rule(
                "multiple_testing_context",
                "statistical_significance",
                "INCONCLUSIVE",
                message="hypothesis family size not declared",
            )
        )
    elif multiple_testing.get("available") and multiple_testing.get("significant_after_correction") is False:
        rules.append(
            _rule(
                "multiple_testing_significance",
                "statistical_significance",
                "FAIL",
                actual=multiple_testing.get("p_value_used_for_correction"),
                threshold=config.significance_level,
                message="robust primary p-value fails multiple-testing correction",
            )
        )
    elif multiple_testing.get("available"):
        rules.append(
            _rule(
                "multiple_testing_context",
                "statistical_significance",
                "PASS",
            )
        )
    else:
        rules.append(
            _rule(
                "multiple_testing_context",
                "statistical_significance",
                "NOT_EVALUATED",
            )
        )
    max_corr = redundancy.get("max_benchmark_correlation")
    if max_corr is not None:
        rules.append(_rule("redundancy", "redundancy", "PASS" if max_corr < 0.95 else "FAIL", actual=max_corr))
    else:
        rules.append(_rule("redundancy", "redundancy", "NOT_EVALUATED", message="no benchmark factors supplied"))

    rules.append(
        _rule(
            "sealed_test",
            "sealed_test",
            "NOT_EVALUATED" if sealed_status == "SEALED" else "PASS",
            message="sealed test not opened" if sealed_status == "SEALED" else "",
        )
    )

    statuses = [r.status for r in rules if r.status not in ("NOT_EVALUATED",)]
    if any(s == "FAIL" for s in statuses):
        overall = "FAIL"
    elif any(s == "INCONCLUSIVE" for s in statuses):
        overall = "INCONCLUSIVE"
    elif statuses and all(s == "PASS" for s in statuses):
        overall = "PASS"
    else:
        overall = "INCONCLUSIVE"

    return AcceptanceGateResult(overall_status=overall, rules=rules, warnings=warnings)
