"""Versioned promising-for-human-review policy."""
from __future__ import annotations

from engines.factor.discovery.validation_models import FactorValidationArtifact
from services.factor_discovery.mining.models import (
    PROMISING_POLICY_VERSION,
    PromisingCandidatePolicy,
    PromisingEvaluationResult,
    PromisingRuleResult,
)


def evaluate_promising(
    artifact: FactorValidationArtifact,
    *,
    policy: PromisingCandidatePolicy | None = None,
    integrity_ok: bool = True,
) -> PromisingEvaluationResult:
    pol = policy or PromisingCandidatePolicy()
    rules: list[PromisingRuleResult] = []
    reason_codes: list[str] = []

    def _rule(rule_id: str, ok: bool | None, actual, threshold, path: str, *, optional: bool = False) -> None:
        if ok is True:
            rules.append(PromisingRuleResult(rule_id=rule_id, status="PASS", actual=actual, threshold=threshold, evidence_path=path))
        elif ok is False:
            rules.append(
                PromisingRuleResult(
                    rule_id=rule_id,
                    status="FAIL",
                    actual=actual,
                    threshold=threshold,
                    evidence_path=path,
                    failure_reason=f"{rule_id}_below_threshold",
                )
            )
            reason_codes.append(rule_id)
        elif optional and pol.allow_inconclusive_optional:
            rules.append(
                PromisingRuleResult(
                    rule_id=rule_id,
                    status="INCONCLUSIVE",
                    actual=actual,
                    threshold=threshold,
                    evidence_path=path,
                    inconclusive_reason="optional_metric_missing",
                )
            )
        else:
            rules.append(
                PromisingRuleResult(
                    rule_id=rule_id,
                    status="NOT_EVALUATED",
                    actual=actual,
                    threshold=threshold,
                    evidence_path=path,
                    inconclusive_reason="missing_metric",
                )
            )
            reason_codes.append(rule_id)

    _rule("integrity", integrity_ok if pol.require_integrity_pass else True, integrity_ok, True, "integrity")
    _rule("closed_artifact", not artifact.sealed_test.opened, not artifact.sealed_test.opened, True, "sealed_test.status")
    cov = artifact.validation_metrics.get("valid_date_count", 0)
    total = artifact.validation_metrics.get("total_dates", 1) or 1
    cov_pct = cov / total if total else 0
    _rule("validation_coverage", cov_pct >= pol.min_valid_date_coverage_pct, round(cov_pct, 4), pol.min_valid_date_coverage_pct, "validation_metrics.valid_date_count")
    ic = artifact.validation_metrics.get("mean_rank_ic")
    _rule("mean_rank_ic", ic is not None and ic >= pol.min_mean_rank_ic, ic, pol.min_mean_rank_ic, "validation_metrics.mean_rank_ic")
    robust = artifact.statistical_results.get("robust_significant")
    if pol.require_robust_significance:
        _rule("robust_significance", bool(robust), robust, True, "statistical_results.robust_significant")
    wf = artifact.walk_forward.get("pass_rate")
    _rule("walk_forward_pass_rate", wf is not None and wf >= pol.min_walk_forward_pass_rate, wf, pol.min_walk_forward_pass_rate, "walk_forward.pass_rate", optional=True)
    turnover = artifact.portfolio_results.get("annualized_turnover")
    _rule("turnover", turnover is not None and turnover <= pol.max_turnover, turnover, pol.max_turnover, "portfolio_results.annualized_turnover", optional=True)
    dd = artifact.portfolio_results.get("max_drawdown")
    _rule("drawdown", dd is not None and abs(float(dd)) <= pol.max_drawdown, dd, pol.max_drawdown, "portfolio_results.max_drawdown", optional=True)
    redundancy = artifact.redundancy.get("max_benchmark_correlation")
    if redundancy is not None:
        _rule("redundancy", redundancy <= pol.max_redundancy, redundancy, pol.max_redundancy, "redundancy.max_benchmark_correlation")
    critical_warnings = [w for w in artifact.warnings if "pit" in w.lower() or "provenance" in w.lower()]
    _rule("pit_provenance", len(critical_warnings) == 0, len(critical_warnings), 0, "warnings")

    hard_fails = [r for r in rules if r.status == "FAIL"]
    if not hard_fails and not reason_codes:
        return PromisingEvaluationResult(overall="PROMISING_FOR_HUMAN_REVIEW", rules=rules, reason_codes=[])
    if hard_fails:
        return PromisingEvaluationResult(overall="NOT_PROMISING", rules=rules, reason_codes=reason_codes)
    return PromisingEvaluationResult(overall="INCONCLUSIVE", rules=rules, reason_codes=reason_codes)
