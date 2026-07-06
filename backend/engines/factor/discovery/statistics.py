"""Statistical helpers for Factor Discovery validation."""
from __future__ import annotations

import math
from typing import Literal

import numpy as np

SIGNIFICANCE_METHOD_VERSION = "factor-significance-v1"
DEFAULT_NEWEY_WEST_LAG_POLICY = "floor_4x_horizon_over_3"


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    arr = np.array(values, dtype=float)
    return float(arr.mean()), float(arr.std(ddof=0))


def standard_error(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    _, std = mean_std(values)
    return std / math.sqrt(len(values))


def t_statistic(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mu, std = mean_std(values)
    if std == 0:
        return None
    return mu / (std / math.sqrt(len(values)))


def two_sided_p_value_from_t(t: float, df: int) -> float | None:
    try:
        from scipy import stats

        return float(2 * stats.t.sf(abs(t), df))
    except Exception:
        # Normal approximation
        from math import erf, sqrt

        z = abs(t)
        p = 2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))
        return float(min(max(p, 0.0), 1.0))


def confidence_interval(values: list[float], alpha: float = 0.05) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    mu, std = mean_std(values)
    se = std / math.sqrt(len(values))
    try:
        from scipy import stats

        t_crit = float(stats.t.ppf(1 - alpha / 2, len(values) - 1))
    except Exception:
        t_crit = 1.96
    return mu - t_crit * se, mu + t_crit * se


def positive_fraction(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(1 for v in values if v > 0) / len(values)


def bonferroni_correction(p_values: list[float], family_size: int, alpha: float) -> list[bool]:
    if family_size <= 0:
        return [False] * len(p_values)
    threshold = alpha / family_size
    return [p <= threshold for p in p_values]


def benjamini_hochberg(p_values: list[float], alpha: float) -> list[bool]:
    n = len(p_values)
    if n == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    passed = [False] * n
    max_k = -1
    for rank, (orig_i, p) in enumerate(indexed, start=1):
        if p <= alpha * rank / n:
            max_k = rank
    if max_k < 0:
        return passed
    for rank, (orig_i, _) in enumerate(indexed, start=1):
        if rank <= max_k:
            passed[orig_i] = True
    return passed


def spearman_monotonicity(quantile_returns: list[float]) -> float | None:
    """Spearman correlation between quantile index and mean return."""
    if len(quantile_returns) < 2:
        return None
    x = np.arange(len(quantile_returns), dtype=float)
    y = np.array(quantile_returns, dtype=float)
    if np.std(y) == 0:
        return None
    rx = pd_rank(x)
    ry = pd_rank(y)
    return float(np.corrcoef(rx, ry)[0, 1])


def newey_west_max_lag(*, horizon_sessions: int, sample_size: int, lag_policy: str) -> int:
    """Explicit lag policy for HAC standard errors."""
    if lag_policy == DEFAULT_NEWEY_WEST_LAG_POLICY:
        lag = max(1, int(math.floor(4 * horizon_sessions / 3)))
    elif lag_policy == "horizon_minus_one":
        lag = max(1, horizon_sessions - 1)
    elif lag_policy.startswith("fixed:"):
        lag = max(1, int(lag_policy.split(":", 1)[1]))
    else:
        lag = max(1, horizon_sessions)
    return min(lag, max(1, sample_size - 1))


def newey_west_variance(values: list[float], *, max_lag: int) -> float | None:
    """Newey–West HAC variance of the sample mean."""
    n = len(values)
    if n < 2:
        return None
    arr = np.asarray(values, dtype=float)
    mu = float(arr.mean())
    demeaned = arr - mu
    gamma0 = float(np.dot(demeaned, demeaned) / n)
    var = gamma0
    lag_cap = min(max_lag, n - 1)
    for lag in range(1, lag_cap + 1):
        weight = 1.0 - lag / (lag_cap + 1)
        cov = float(np.dot(demeaned[:-lag], demeaned[lag:]) / n)
        var += 2.0 * weight * cov
    return var / n


def newey_west_mean_se(values: list[float], *, max_lag: int) -> float | None:
    var = newey_west_variance(values, max_lag=max_lag)
    if var is None or var <= 0:
        return None
    return math.sqrt(var)


def newey_west_t_stat(values: list[float], *, max_lag: int) -> float | None:
    if len(values) < 2:
        return None
    mu, _ = mean_std(values)
    se = newey_west_mean_se(values, max_lag=max_lag)
    if se is None or se == 0:
        return None
    return mu / se


def non_overlapping_subsample(values: list[float], *, stride: int) -> list[float]:
    if stride <= 1:
        return list(values)
    return [values[i] for i in range(0, len(values), stride)]


def resolve_primary_significance(
    values: list[float],
    *,
    method: Literal["newey_west", "non_overlapping", "naive_descriptive"],
    horizon_sessions: int,
    newey_west_lag_policy: str,
) -> dict[str, float | int | str | None]:
    """Primary (robust) and descriptive significance paths."""
    n = len(values)
    mu, std = mean_std(values) if values else (0.0, 0.0)
    descriptive_t = t_statistic(values)
    descriptive_p = (
        two_sided_p_value_from_t(descriptive_t, n - 1) if descriptive_t is not None and n >= 2 else None
    )
    result: dict[str, float | int | str | None] = {
        "sample_size": n,
        "mean": round(mu, 6) if values else None,
        "std": round(std, 6) if values else None,
        "descriptive_t_stat": round(descriptive_t, 4) if descriptive_t is not None else None,
        "descriptive_p_value": round(descriptive_p, 6) if descriptive_p is not None else None,
        "primary_method": method,
        "primary_t_stat": None,
        "primary_p_value": None,
        "newey_west_lag": None,
        "newey_west_lag_policy": newey_west_lag_policy if method == "newey_west" else None,
        "non_overlapping_stride": None,
        "non_overlapping_sample_size": None,
    }
    if method == "naive_descriptive":
        result["primary_t_stat"] = result["descriptive_t_stat"]
        result["primary_p_value"] = result["descriptive_p_value"]
        return result
    if method == "newey_west":
        lag = newey_west_max_lag(
            horizon_sessions=horizon_sessions,
            sample_size=n,
            lag_policy=newey_west_lag_policy,
        )
        t_robust = newey_west_t_stat(values, max_lag=lag)
        p_robust = two_sided_p_value_from_t(t_robust, max(1, n - 1)) if t_robust is not None else None
        result["newey_west_lag"] = lag
        result["primary_t_stat"] = round(t_robust, 4) if t_robust is not None else None
        result["primary_p_value"] = round(p_robust, 6) if p_robust is not None else None
        return result
    stride = max(1, horizon_sessions)
    subsample = non_overlapping_subsample(values, stride=stride)
    t_sub = t_statistic(subsample)
    p_sub = two_sided_p_value_from_t(t_sub, len(subsample) - 1) if t_sub is not None and len(subsample) >= 2 else None
    result["non_overlapping_stride"] = stride
    result["non_overlapping_sample_size"] = len(subsample)
    result["primary_t_stat"] = round(t_sub, 4) if t_sub is not None else None
    result["primary_p_value"] = round(p_sub, 6) if p_sub is not None else None
    return result


def pd_rank(arr: np.ndarray) -> np.ndarray:
    order = np.argsort(arr, kind="mergesort")
    ranks = np.empty(len(arr), dtype=float)
    i = 0
    while i < len(arr):
        j = i
        while j + 1 < len(arr) and arr[order[j + 1]] == arr[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks
