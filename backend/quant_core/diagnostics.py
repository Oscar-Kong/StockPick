"""Statistical diagnostics for return series."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from quant_core.returns import _as_returns_series


def _clean(values) -> np.ndarray:
    return _as_returns_series(values).dropna().to_numpy()


def skewness(values) -> float:
    """Sample skewness (Fisher-Pearson)."""
    arr = _clean(values)
    if len(arr) < 3:
        return 0.0
    m = arr.mean()
    sd = arr.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(np.mean(((arr - m) / sd) ** 3))


def excess_kurtosis(values) -> float:
    """Excess kurtosis (normal distribution = 0)."""
    arr = _clean(values)
    if len(arr) < 4:
        return 0.0
    m = arr.mean()
    sd = arr.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(np.mean(((arr - m) / sd) ** 4) - 3.0)


def jarque_bera_test(values) -> dict[str, Any]:
    """
    Jarque-Bera normality test.

    Uses scipy.stats.jarque_bera when available; otherwise returns a numpy fallback.
    """
    arr = _clean(values)
    if len(arr) < 8:
        return {
            "available": False,
            "statistic": None,
            "pvalue": None,
            "reason": "insufficient_observations",
        }
    try:
        from scipy import stats

        stat, pvalue = stats.jarque_bera(arr)
        return {
            "available": True,
            "engine": "scipy",
            "statistic": float(stat),
            "pvalue": float(pvalue),
            "n": len(arr),
        }
    except Exception:
        n = len(arr)
        s = skewness(arr)
        k = excess_kurtosis(arr)
        jb = n / 6.0 * (s**2 + (k**2) / 4.0)
        return {
            "available": True,
            "engine": "fallback",
            "statistic": float(jb),
            "pvalue": None,
            "n": n,
        }


def autocorrelation_summary(values, max_lag: int = 20) -> dict[str, Any]:
    """Autocorrelation coefficients for lags 1..max_lag."""
    if max_lag <= 0:
        raise ValueError("max_lag must be positive")
    s = _as_returns_series(values).dropna()
    if len(s) < 2:
        return {"lags": [], "acf": [], "n": len(s)}
    lags = list(range(1, min(max_lag, len(s) - 1) + 1))
    acf = [float(s.autocorr(lag=lag)) for lag in lags]
    significant = [lag for lag, coef in zip(lags, acf) if coef is not None and abs(coef) > 0.2]
    return {
        "lags": lags,
        "acf": acf,
        "n": int(len(s)),
        "significant_lags": significant,
    }


def adf_test(values, *, maxlag: int | None = None) -> dict[str, Any]:
    """
    Augmented Dickey-Fuller stationarity test via statsmodels when available.
    """
    arr = _clean(values)
    if len(arr) < 10:
        return {
            "available": False,
            "statistic": None,
            "pvalue": None,
            "reason": "insufficient_observations",
        }
    try:
        from statsmodels.tsa.stattools import adfuller

        result = adfuller(arr, maxlag=maxlag, autolag="AIC")
        return {
            "available": True,
            "engine": "statsmodels",
            "statistic": float(result[0]),
            "pvalue": float(result[1]),
            "used_lag": int(result[2]),
            "nobs": int(result[3]),
            "critical_values": {k: float(v) for k, v in result[4].items()},
            "stationary_5pct": float(result[0]) < float(result[4]["5%"]),
        }
    except Exception as exc:
        return {
            "available": False,
            "statistic": None,
            "pvalue": None,
            "reason": str(exc),
        }
