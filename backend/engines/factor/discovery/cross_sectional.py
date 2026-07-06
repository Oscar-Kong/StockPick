"""Cross-sectional operator execution by date."""
from __future__ import annotations

import numpy as np
import pandas as pd

from engines.factor.discovery.panel_models import FactorExecutionConfig, OperatorDiagnosticsCollector


def _rank_average(values: np.ndarray) -> np.ndarray:
    """Average ranks (1-based), stable mergesort."""
    n = len(values)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _eligible_values(series: pd.Series, eligibility: pd.Series) -> pd.Series:
    return series.where(eligibility.astype(bool))


def _by_date(series: pd.Series, eligibility: pd.Series):
    masked = _eligible_values(series, eligibility)
    dates = masked.index.get_level_values(0).unique()
    for d in dates:
        idx = masked.index[masked.index.get_level_values(0) == d]
        yield d, masked.loc[idx]


def apply_rank(series: pd.Series, eligibility: pd.Series, config: FactorExecutionConfig, diag: OperatorDiagnosticsCollector) -> pd.Series:
    """Ordinal average-rank normalized to [0, 1] via (rank-1)/(n-1)."""
    out = pd.Series(np.nan, index=series.index, dtype=float)
    for _d, day_vals in _by_date(series, eligibility):
        vals = day_vals.dropna()
        if len(vals) < config.min_cross_sectional_observations:
            diag.insufficient_cross_section_count += 1
            continue
        ranks = _rank_average(vals.to_numpy(dtype=float))
        norm = np.array([0.5]) if len(vals) == 1 else (ranks - 1.0) / (len(vals) - 1.0)
        out.loc[vals.index] = norm
    return out


def apply_percentile_rank(
    series: pd.Series,
    eligibility: pd.Series,
    config: FactorExecutionConfig,
    diag: OperatorDiagnosticsCollector,
) -> pd.Series:
    out = pd.Series(np.nan, index=series.index, dtype=float)
    for _d, day_vals in _by_date(series, eligibility):
        vals = day_vals.dropna()
        if len(vals) < config.min_cross_sectional_observations:
            diag.insufficient_cross_section_count += 1
            continue
        ranks = _rank_average(vals.to_numpy(dtype=float))
        pct = np.array([1.0]) if len(vals) == 1 else (ranks - 1.0) / (len(vals) - 1.0)
        out.loc[vals.index] = pct
    return out


def apply_zscore(
    series: pd.Series,
    eligibility: pd.Series,
    config: FactorExecutionConfig,
    diag: OperatorDiagnosticsCollector,
) -> pd.Series:
    out = pd.Series(np.nan, index=series.index, dtype=float)
    for _d, day_vals in _by_date(series, eligibility):
        vals = day_vals.dropna()
        if len(vals) < config.min_cross_sectional_observations:
            diag.insufficient_cross_section_count += 1
            continue
        mu = float(vals.mean())
        sigma = float(vals.std(ddof=0))
        if sigma == 0.0 or not np.isfinite(sigma):
            diag.zero_variance_zscore_count += 1
            if config.zero_variance_zscore == "zero":
                out.loc[vals.index] = 0.0
            continue
        out.loc[vals.index] = (vals - mu) / sigma
    return out


def apply_winsorize(
    series: pd.Series,
    eligibility: pd.Series,
    lower: float,
    upper: float,
    config: FactorExecutionConfig,
    diag: OperatorDiagnosticsCollector,
) -> pd.Series:
    out = pd.Series(np.nan, index=series.index, dtype=float)
    for _d, day_vals in _by_date(series, eligibility):
        vals = day_vals.dropna()
        if len(vals) < config.min_cross_sectional_observations:
            diag.insufficient_cross_section_count += 1
            continue
        lo = float(vals.quantile(lower))
        hi = float(vals.quantile(upper))
        out.loc[vals.index] = vals.clip(lower=lo, upper=hi)
    return out
