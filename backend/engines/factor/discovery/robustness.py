"""Robustness breakdowns for Factor Discovery validation."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engines.factor.discovery.metrics_adapter import evaluate_cross_sectional_metrics
from engines.factor.discovery.periods import mask_for_sessions
from engines.factor.discovery.quantiles import evaluate_quantiles
from engines.factor.discovery.validation_models import FactorValidationConfig


def _market_cap_bucket(mcap: float, *, small: float = 2e9, large: float = 10e9) -> str:
    if np.isnan(mcap):
        return "UNKNOWN"
    if mcap < small:
        return "SMALL"
    if mcap < large:
        return "MID"
    return "LARGE"


def evaluate_robustness(
    scores: pd.Series,
    outcome_panel,
    panel_frame: pd.DataFrame,
    *,
    period_mask: pd.Series,
    config: FactorValidationConfig,
    direction: str,
    min_slice_dates: int = 5,
) -> dict[str, Any]:
    slices: dict[str, Any] = {}
    df = panel_frame.copy()
    df["score"] = scores
    df = df[period_mask.reindex(df.index, fill_value=False)]

    # Calendar year
    for year, grp in df.groupby(df.index.get_level_values(0).year):
        dates = tuple(sorted({pd.Timestamp(d).strftime("%Y-%m-%d") for d in grp.index.get_level_values(0)}))
        if len(dates) < min_slice_dates:
            slices[f"year_{year}"] = {"status": "INSUFFICIENT_DATA", "date_count": len(dates)}
            continue
        m = mask_for_sessions(scores.index, dates)
        ic = evaluate_cross_sectional_metrics(scores, outcome_panel, period_mask=m, config=config, direction=direction)
        q = evaluate_quantiles(scores, outcome_panel, period_mask=m, config=config, direction=direction)
        slices[f"year_{year}"] = {
            "status": "OK",
            "date_count": len(dates),
            "mean_rank_ic": ic.get("mean_rank_ic"),
            "spread": q.get("mean_top_minus_bottom_spread"),
            "coverage": ic.get("valid_date_count"),
        }

    # Sector (PIT-safe only when sector column present)
    if "sector" in df.columns:
        for sector, grp in df.groupby("sector"):
            dates = tuple(sorted({pd.Timestamp(d).strftime("%Y-%m-%d") for d in grp.index.get_level_values(0)}))
            if len(dates) < min_slice_dates:
                slices[f"sector_{sector}"] = {"status": "INSUFFICIENT_DATA"}
                continue
            m = mask_for_sessions(scores.index, dates)
            ic = evaluate_cross_sectional_metrics(scores, outcome_panel, period_mask=m, config=config, direction=direction)
            slices[f"sector_{sector}"] = {
                "status": "OK",
                "mean_rank_ic": ic.get("mean_rank_ic"),
                "observation_count": int(len(grp)),
            }

    # Market-cap bucket per score date
    if "market_cap" in df.columns:
        bucket_dates: dict[str, set[str]] = {}
        for (dt, sym), row in df.iterrows():
            b = _market_cap_bucket(float(row.get("market_cap", np.nan)))
            bucket_dates.setdefault(b, set()).add(pd.Timestamp(dt).strftime("%Y-%m-%d"))
        for bucket, date_set in bucket_dates.items():
            dates = tuple(sorted(date_set))
            if len(dates) < min_slice_dates:
                slices[f"mcap_{bucket}"] = {"status": "INSUFFICIENT_DATA"}
                continue
            m = mask_for_sessions(scores.index, dates)
            ic = evaluate_cross_sectional_metrics(scores, outcome_panel, period_mask=m, config=config, direction=direction)
            slices[f"mcap_{bucket}"] = {"status": "OK", "mean_rank_ic": ic.get("mean_rank_ic")}

    return {"slices": slices}
