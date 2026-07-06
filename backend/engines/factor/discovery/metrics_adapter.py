"""Cross-sectional IC metrics adapter for Factor Discovery validation."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engines.factor.discovery.statistics import (
    benjamini_hochberg,
    bonferroni_correction,
    confidence_interval,
    mean_std,
    positive_fraction,
    resolve_primary_significance,
    standard_error,
    t_statistic,
    two_sided_p_value_from_t,
)
from engines.factor.discovery.validation_models import FactorValidationConfig
from services.walk_forward_research_service import cross_section_metrics


def orient_factor_scores(
    raw_scores: pd.Series,
    *,
    direction: str,
) -> pd.Series:
    if direction == "LOWER_IS_BETTER":
        return -raw_scores
    return raw_scores


def _per_date_ic(
    scores: pd.Series,
    outcomes: pd.Series,
    valid: pd.Series,
    eligibility: pd.Series,
    *,
    min_obs: int,
) -> list[dict[str, Any]]:
    df = pd.DataFrame(
        {
            "score": scores,
            "fwd": outcomes,
            "valid": valid.astype(bool),
            "eligible": eligibility.astype(bool),
        }
    )
    df = df[df["eligible"] & df["valid"] & df["score"].notna() & df["fwd"].notna()]
    rows: list[dict[str, Any]] = []
    for dt, grp in df.groupby(level=0):
        if len(grp) < min_obs:
            rows.append({"date": str(pd.Timestamp(dt).date()), "sufficient": False, "n": len(grp)})
            continue
        m = cross_section_metrics(grp["score"].tolist(), grp["fwd"].tolist())
        m["date"] = str(pd.Timestamp(dt).date())
        rows.append(m)
    return rows


def summarize_ic_series(
    per_date: list[dict[str, Any]],
    *,
    config: FactorValidationConfig | None = None,
) -> dict[str, Any]:
    rank_ics = [float(r["rank_ic"]) for r in per_date if r.get("sufficient")]
    pearson_ics = [float(r["pearson_ic"]) for r in per_date if r.get("sufficient")]
    insufficient = sum(1 for r in per_date if not r.get("sufficient"))
    if not rank_ics:
        return {
            "sufficient": False,
            "valid_date_count": 0,
            "insufficient_date_count": insufficient,
            "total_dates": len(per_date),
        }
    mu_r, std_r = mean_std(rank_ics)
    mu_p, std_p = mean_std(pearson_ics)
    ir_r = mu_r / std_r if std_r > 0 else None
    ir_p = mu_p / std_p if std_p > 0 else None
    t_r = t_statistic(rank_ics)
    p_r = two_sided_p_value_from_t(t_r, len(rank_ics) - 1) if t_r is not None else None
    ci_r = confidence_interval(rank_ics)
    significance: dict[str, Any] = {}
    if config is not None:
        significance = resolve_primary_significance(
            rank_ics,
            method=config.primary_significance_method,
            horizon_sessions=config.primary_horizon_sessions,
            newey_west_lag_policy=config.newey_west_lag_policy,
        )
    return {
        "sufficient": True,
        "valid_date_count": len(rank_ics),
        "insufficient_date_count": insufficient,
        "total_dates": len(per_date),
        "mean_rank_ic": round(mu_r, 6),
        "mean_pearson_ic": round(mu_p, 6),
        "rank_ic_std": round(std_r, 6),
        "pearson_ic_std": round(std_p, 6),
        "rank_ic_ir": round(ir_r, 6) if ir_r is not None else None,
        "pearson_ic_ir": round(ir_p, 6) if ir_p is not None else None,
        "positive_rank_ic_pct": round(positive_fraction(rank_ics), 4),
        "positive_pearson_ic_pct": round(positive_fraction(pearson_ics), 4),
        "rank_ic_se": round(standard_error(rank_ics), 6),
        "rank_ic_t_stat": round(t_r, 4) if t_r is not None else None,
        "rank_ic_p_value": round(p_r, 6) if p_r is not None else None,
        "rank_ic_ci_95": [round(ci_r[0], 6), round(ci_r[1], 6)] if ci_r else None,
        "rank_ic_significance": significance,
        "rank_ic_p_value_primary": significance.get("primary_p_value"),
        "rank_ic_t_stat_primary": significance.get("primary_t_stat"),
        "per_date": per_date,
        "naive_t_stat_note": "descriptive t-stat on overlapping horizons — not used for strict acceptance",
    }


def evaluate_cross_sectional_metrics(
    scores: pd.Series,
    outcome_panel,
    *,
    period_mask: pd.Series,
    config: FactorValidationConfig,
    direction: str,
) -> dict[str, Any]:
    oriented = orient_factor_scores(scores, direction=direction)
    mask = period_mask.reindex(scores.index, fill_value=False)
    per_date = _per_date_ic(
        oriented[mask],
        outcome_panel.forward_return[mask],
        outcome_panel.outcome_valid[mask],
        outcome_panel.eligibility_at_score[mask],
        min_obs=config.min_cross_sectional_observations,
    )
    summary = summarize_ic_series(per_date, config=config)
    summary["direction"] = direction
    summary["orientation"] = "negated" if direction == "LOWER_IS_BETTER" else "identity"
    return summary
