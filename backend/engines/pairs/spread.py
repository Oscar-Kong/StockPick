"""Spread construction, z-score, and mean-reversion half-life."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MIN_OBS_SPREAD = 30
MIN_OBS_HALFLIFE = 20


def estimate_hedge_ratio(y: pd.Series, x: pd.Series) -> tuple[float, float]:
    """OLS hedge ratio and intercept: y = intercept + beta * x."""
    aligned = pd.concat([y, x], axis=1, join="inner").dropna()
    if aligned.empty:
        return 0.0, 0.0
    y_arr = aligned.iloc[:, 0].to_numpy(dtype=float)
    x_arr = aligned.iloc[:, 1].to_numpy(dtype=float)
    x_mat = np.column_stack([np.ones(len(x_arr)), x_arr])
    coef, _, _, _ = np.linalg.lstsq(x_mat, y_arr, rcond=None)
    return float(coef[0]), float(coef[1])


def build_spread(
    y: pd.Series,
    x: pd.Series,
    *,
    hedge_ratio: float,
    intercept: float = 0.0,
) -> pd.Series:
    """Spread = y - intercept - hedge_ratio * x on aligned observations."""
    aligned = pd.concat([y, x], axis=1, join="inner").dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    spread = aligned.iloc[:, 0] - intercept - hedge_ratio * aligned.iloc[:, 1]
    spread.name = "spread"
    return spread


def spread_zscore(spread: pd.Series, window: int = 60) -> dict[str, Any]:
    """Rolling z-score of spread; returns latest value and series stats."""
    if spread is None or spread.empty or len(spread) < MIN_OBS_SPREAD:
        return {
            "sufficient": False,
            "window": window,
            "latest_z_score": None,
            "spread_mean": None,
            "spread_std": None,
            "warning": "insufficient_spread_history",
        }

    win = min(window, len(spread))
    roll_mean = spread.rolling(win, min_periods=max(10, win // 2)).mean()
    roll_std = spread.rolling(win, min_periods=max(10, win // 2)).std(ddof=1)
    z = (spread - roll_mean) / roll_std.replace(0, np.nan)
    latest = z.iloc[-1]
    if not np.isfinite(latest):
        return {
            "sufficient": False,
            "window": win,
            "latest_z_score": None,
            "spread_mean": round(float(spread.mean()), 6),
            "spread_std": round(float(spread.std(ddof=1)), 6) if len(spread) > 1 else None,
            "warning": "undefined_z_score",
        }

    return {
        "sufficient": True,
        "window": win,
        "latest_z_score": round(float(latest), 4),
        "spread_mean": round(float(spread.mean()), 6),
        "spread_std": round(float(spread.std(ddof=1)), 6),
        "warning": None,
    }


def estimate_half_life(spread: pd.Series) -> dict[str, Any]:
    """
    AR(1) mean-reversion half-life in sessions.

    Regresses delta(spread) on lagged spread; half_life = -ln(2) / beta when beta < 0.
    """
    s = spread.dropna()
    if len(s) < MIN_OBS_HALFLIFE:
        return {
            "sufficient": False,
            "half_life_sessions": None,
            "mean_reverting": False,
            "warning": "insufficient_observations",
        }

    lag = s.shift(1)
    delta = s.diff()
    aligned = pd.concat([delta, lag], axis=1, join="inner").dropna()
    aligned.columns = ["delta", "lag"]
    if len(aligned) < MIN_OBS_HALFLIFE:
        return {
            "sufficient": False,
            "half_life_sessions": None,
            "mean_reverting": False,
            "warning": "insufficient_observations",
        }

    y = aligned["delta"].to_numpy(dtype=float)
    x = aligned["lag"].to_numpy(dtype=float)
    x_mat = np.column_stack([np.ones(len(x)), x])
    coef, _, _, _ = np.linalg.lstsq(x_mat, y, rcond=None)
    beta = float(coef[1])

    if beta >= 0:
        return {
            "sufficient": True,
            "half_life_sessions": None,
            "mean_reverting": False,
            "beta": round(beta, 6),
            "warning": "not_mean_reverting",
        }

    half_life = -np.log(2.0) / beta
    if not np.isfinite(half_life) or half_life <= 0:
        return {
            "sufficient": True,
            "half_life_sessions": None,
            "mean_reverting": True,
            "beta": round(beta, 6),
            "warning": "invalid_half_life",
        }

    return {
        "sufficient": True,
        "half_life_sessions": round(float(half_life), 2),
        "mean_reverting": True,
        "beta": round(beta, 6),
        "warning": None,
    }
