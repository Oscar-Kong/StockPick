"""Engle-Granger cointegration tests for pair candidates."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from quant_core.diagnostics import adf_test

MIN_OBS_COINT = 60


def _ols_hedge(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    """OLS: y = intercept + hedge_ratio * x."""
    x_mat = np.column_stack([np.ones(len(x)), x])
    coef, _, _, _ = np.linalg.lstsq(x_mat, y, rcond=None)
    intercept = float(coef[0])
    hedge_ratio = float(coef[1])
    return intercept, hedge_ratio


def engle_granger_test(
    y: pd.Series | np.ndarray,
    x: pd.Series | np.ndarray,
) -> dict[str, Any]:
    """
    Engle-Granger two-step cointegration test.

    Uses statsmodels ``coint`` when available; otherwise OLS residuals + ADF fallback.
    """
    y_arr = np.asarray(y, dtype=float)
    x_arr = np.asarray(x, dtype=float)
    mask = np.isfinite(y_arr) & np.isfinite(x_arr)
    y_arr = y_arr[mask]
    x_arr = x_arr[mask]
    n = len(y_arr)

    if n < MIN_OBS_COINT:
        return {
            "sufficient": False,
            "observations": n,
            "hedge_ratio": None,
            "intercept": None,
            "p_value": None,
            "cointegrated_5pct": False,
            "engine": None,
            "warning": "insufficient_observations",
        }

    intercept, hedge_ratio = _ols_hedge(y_arr, x_arr)

    try:
        from statsmodels.tsa.stattools import coint

        _score, p_value, _crit = coint(y_arr, x_arr)
        return {
            "sufficient": True,
            "observations": n,
            "hedge_ratio": round(hedge_ratio, 6),
            "intercept": round(intercept, 6),
            "p_value": round(float(p_value), 6),
            "cointegrated_5pct": float(p_value) < 0.05,
            "engine": "statsmodels",
            "warning": None,
        }
    except Exception:
        pass

    residuals = y_arr - (intercept + hedge_ratio * x_arr)
    adf = adf_test(residuals)
    if not adf.get("available"):
        return {
            "sufficient": False,
            "observations": n,
            "hedge_ratio": round(hedge_ratio, 6),
            "intercept": round(intercept, 6),
            "p_value": None,
            "cointegrated_5pct": False,
            "engine": "fallback_adf",
            "warning": adf.get("reason", "adf_unavailable"),
        }

    p_value = adf.get("pvalue")
    return {
        "sufficient": True,
        "observations": n,
        "hedge_ratio": round(hedge_ratio, 6),
        "intercept": round(intercept, 6),
        "p_value": round(float(p_value), 6) if p_value is not None else None,
        "cointegrated_5pct": bool(adf.get("stationary_5pct")),
        "engine": "fallback_adf",
        "warning": None,
    }


def statsmodels_available() -> bool:
    try:
        from statsmodels.tsa.stattools import coint  # noqa: F401

        return True
    except Exception:
        return False
