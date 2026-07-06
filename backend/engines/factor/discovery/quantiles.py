"""Quantile analysis for Factor Discovery validation."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engines.factor.discovery.statistics import spearman_monotonicity
from engines.factor.discovery.validation_models import FactorValidationConfig
from services.scan_evaluation_metrics import score_decile_breakdown
from services.walk_forward_research_service import turnover_rate


def evaluate_quantiles(
    scores: pd.Series,
    outcome_panel,
    *,
    period_mask: pd.Series,
    config: FactorValidationConfig,
    direction: str,
) -> dict[str, Any]:
    from engines.factor.discovery.metrics_adapter import orient_factor_scores

    oriented = orient_factor_scores(scores, direction=direction)
    mask = period_mask.reindex(scores.index, fill_value=False)
    df = pd.DataFrame(
        {
            "score": oriented[mask],
            "fwd": outcome_panel.forward_return[mask],
            "valid": outcome_panel.outcome_valid[mask],
            "eligible": outcome_panel.eligibility_at_score[mask],
        }
    )
    df = df[df["eligible"] & df["valid"] & df["score"].notna() & df["fwd"].notna()]

    per_date_spreads: list[float] = []
    per_date_monotonic: list[float] = []
    quantile_returns_acc: dict[int, list[float]] = {}
    quantile_counts: dict[int, int] = {}
    turnover_vals: list[float] = []
    prev_top: set[str] | None = None

    for dt, grp in df.groupby(level=0):
        if len(grp) < config.min_cross_sectional_observations:
            continue
        breakdown = score_decile_breakdown(
            grp["score"].tolist(),
            grp["fwd"].tolist(),
            n_deciles=config.quantile_count,
        )
        if not breakdown.get("sufficient"):
            continue
        spread = breakdown.get("top_minus_bottom_spread_pct")
        if spread is not None:
            per_date_spreads.append(float(spread))
        deciles = breakdown.get("deciles") or []
        rets = [d["avg_forward_return_pct"] for d in deciles]
        mono = spearman_monotonicity(rets)
        if mono is not None:
            per_date_monotonic.append(mono)
        for d in deciles:
            q = int(d["decile"])
            quantile_returns_acc.setdefault(q, []).append(float(d["avg_forward_return_pct"]))
            quantile_counts[q] = quantile_counts.get(q, 0) + int(d["count"])
        top_syms = set(
            grp.nlargest(max(1, int(len(grp) * config.top_quantile_fraction)), "score").index.get_level_values(1)
        )
        if prev_top is not None:
            turnover_vals.append(turnover_rate(prev_top, top_syms))
        prev_top = top_syms

    quantile_summary = []
    for q in sorted(quantile_returns_acc):
        vals = quantile_returns_acc[q]
        quantile_summary.append(
            {
                "quantile": q,
                "mean_return": round(float(np.mean(vals)), 6),
                "observation_count": quantile_counts.get(q, 0),
            }
        )

    overall_spread = None
    if quantile_summary:
        overall_spread = quantile_summary[-1]["mean_return"] - quantile_summary[0]["mean_return"]

    return {
        "quantile_count": config.quantile_count,
        "quantiles": quantile_summary,
        "mean_top_minus_bottom_spread": round(float(np.mean(per_date_spreads)), 6) if per_date_spreads else None,
        "monotonicity_spearman_mean": round(float(np.mean(per_date_monotonic)), 4) if per_date_monotonic else None,
        "extreme_order_correct_pct": round(
            sum(1 for s in per_date_spreads if s > 0) / len(per_date_spreads), 4
        )
        if per_date_spreads
        else None,
        "quantile_turnover_mean": round(float(np.mean(turnover_vals)), 4) if turnover_vals else None,
        "overall_spread": round(overall_spread, 6) if overall_spread is not None else None,
        "valid_dates": len(per_date_spreads),
    }
