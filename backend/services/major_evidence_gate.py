"""Deterministic Major Evidence Gate — no LLM involvement."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from models.schemas_research import EvidenceImpact, MajorEvidenceGateResult

MIN_SAMPLE_SIZE = 30
MIN_SCORED_PERIODS = 3
MIN_EFFECT_IC = 0.02
IC_STALE_DAYS = 7
WF_STALE_DAYS = 30


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _days_since(value: str | date | datetime | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, date):
        d = value
    else:
        parsed = _parse_date(str(value))
        if parsed is None:
            return None
        d = parsed
    return (_utc_today() - d).days


def evaluate_integrity_blockers(
    *,
    run_type: str,
    summary: dict[str, Any],
    parameters: dict[str, Any],
    warnings: list[str],
    blockers: list[str],
) -> MajorEvidenceGateResult:
    """Fast-path integrity evaluation — may block before major-effect review."""
    blocking: list[str] = []
    codes: list[str] = []

    for flag in blockers:
        blocking.append(f"explicit_blocker:{flag}")

    warning_text = " ".join(warnings).lower()
    if "leakage" in warning_text or "look-ahead" in warning_text or "look ahead" in warning_text:
        blocking.append("unresolved_leakage_warning")
        codes.append("leakage_warning")

    if run_type == "factor_ic_panel":
        as_of = summary.get("as_of_date") or parameters.get("as_of_date")
        age = _days_since(as_of)
        if age is not None and age > IC_STALE_DAYS:
            blocking.append("stale_factor_ic_data")
            codes.append("stale_ic")

    finished = summary.get("finished_at") or parameters.get("finished_at")
    if run_type == "walk_forward" and finished:
        age = _days_since(finished)
        if age is not None and age > WF_STALE_DAYS:
            codes.append("stale_walk_forward")

    sample = summary.get("sample_size") or summary.get("periods_scored") or summary.get("sample_n")
    if sample is not None and int(sample) < 5 and run_type in ("walk_forward", "prediction_outcomes"):
        blocking.append("insufficient_trustworthy_inputs")
        codes.append("tiny_sample")

    if blocking:
        return MajorEvidenceGateResult(
            impact_level="integrity_blocker",
            passed_checks=[],
            failed_checks=[],
            blocking_checks=blocking,
            explanation_codes=codes or ["integrity_blocker"],
            review_required=True,
        )

    return MajorEvidenceGateResult(
        impact_level="informational",
        passed_checks=["no_integrity_blockers"],
        failed_checks=[],
        blocking_checks=[],
        explanation_codes=["integrity_clear"],
        review_required=False,
    )


def evaluate_major_evidence_gate(
    *,
    run_type: str,
    summary: dict[str, Any],
    parameters: dict[str, Any],
    warnings: list[str] | None = None,
    blockers: list[str] | None = None,
    positive_direction: bool | None = None,
) -> MajorEvidenceGateResult:
    """Evaluate whether evidence may qualify for major positive/negative impact."""
    warnings = list(warnings or [])
    blockers = list(blockers or [])

    integrity = evaluate_integrity_blockers(
        run_type=run_type,
        summary=summary,
        parameters=parameters,
        warnings=warnings,
        blockers=blockers,
    )
    if integrity.blocking_checks:
        return integrity

    passed: list[str] = ["integrity_clear"]
    failed: list[str] = []
    codes: list[str] = []

    # Reproducible saved parameters
    if parameters:
        passed.append("reproducible_parameters")
    else:
        failed.append("reproducible_parameters")

    strategy_v = summary.get("strategy_version") or parameters.get("strategy_version")
    factor_v = summary.get("factor_model_version") or parameters.get("factor_model_version")
    if strategy_v and factor_v:
        passed.append("known_model_versions")
    else:
        failed.append("known_model_versions")

    sample = (
        summary.get("sample_size")
        or summary.get("periods_scored")
        or summary.get("sample_n")
        or summary.get("outcomes_count")
    )
    if sample is not None and int(sample) >= MIN_SAMPLE_SIZE:
        passed.append("minimum_sample_size")
    else:
        failed.append("minimum_sample_size")

    if run_type == "walk_forward":
        periods = int(summary.get("periods_scored") or 0)
        if periods >= MIN_SCORED_PERIODS:
            passed.append("multiple_non_overlapping_periods")
        else:
            failed.append("multiple_non_overlapping_periods")

        end_date = summary.get("end_date") or parameters.get("end_date")
        end = _parse_date(end_date)
        if end and end < _utc_today():
            passed.append("out_of_sample_end_date")
        else:
            failed.append("out_of_sample_end_date")

        agg = summary.get("aggregate_horizons") or {}
        ics: list[float] = []
        for stats in agg.values():
            if isinstance(stats, dict) and stats.get("mean_rank_ic") is not None:
                ics.append(float(stats["mean_rank_ic"]))
        if ics:
            if positive_direction is None:
                positive_direction = sum(ics) >= 0
            same_sign = all(ic >= 0 for ic in ics) or all(ic <= 0 for ic in ics)
            if same_sign:
                passed.append("directional_consistency")
            else:
                failed.append("directional_consistency")
            max_ic = max(abs(ic) for ic in ics)
            if max_ic >= MIN_EFFECT_IC:
                passed.append("meaningful_effect_size")
            else:
                failed.append("meaningful_effect_size")
        else:
            failed.extend(["directional_consistency", "meaningful_effect_size"])

        if summary.get("mean_turnover") is not None:
            passed.append("turnover_analyzed")
        else:
            failed.append("realistic_costs_or_turnover")

        if parameters.get("sleeve") or summary.get("sleeve"):
            passed.append("regime_coverage_metadata")
        else:
            failed.append("regime_coverage_metadata")

    elif run_type == "factor_ic_panel":
        mean_ic = summary.get("mean_ic")
        if mean_ic is not None and abs(float(mean_ic)) >= MIN_EFFECT_IC:
            passed.append("meaningful_effect_size")
            if positive_direction is None:
                positive_direction = float(mean_ic) >= 0
        else:
            failed.append("meaningful_effect_size")
        if summary.get("as_of_date"):
            passed.append("data_cutoff_recorded")
        else:
            failed.append("data_cutoff_recorded")

    elif run_type == "pairs":
        coint = int(summary.get("cointegrated_count") or 0)
        if coint >= 1:
            passed.append("pairs_found")
        else:
            failed.append("pairs_found")

    elif run_type == "prediction_outcomes":
        err = summary.get("mean_prediction_error_pct")
        if err is not None:
            passed.append("calibration_metric_available")
            if positive_direction is None:
                positive_direction = abs(float(err)) < 10.0
        else:
            failed.append("calibration_metric_available")

    else:
        codes.append("generic_gate_minimal")

    leakage_clear = "unresolved_leakage_warning" not in integrity.blocking_checks
    if leakage_clear:
        passed.append("no_unresolved_leakage")
    else:
        failed.append("no_unresolved_leakage")

    review_required = len(failed) > 0
    major_threshold = max(3, len(passed) // 2 + 1)
    qualifies_major = len(failed) == 0 and len(passed) >= major_threshold

    if qualifies_major and positive_direction is not None:
        impact: EvidenceImpact = "major_positive" if positive_direction else "major_negative"
        codes.append("major_gate_passed")
    else:
        impact = "informational"
        codes.append("major_gate_not_passed")

    return MajorEvidenceGateResult(
        impact_level=impact,
        passed_checks=passed,
        failed_checks=failed,
        blocking_checks=[],
        explanation_codes=codes,
        review_required=review_required or impact in ("major_positive", "major_negative"),
    )
