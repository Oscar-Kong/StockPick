"""Lightweight time-series feature helpers built on pandas."""
from __future__ import annotations

import pandas as pd

from quant_core.returns import _as_series


def lag(values, periods: int = 1) -> pd.Series:
    """Shift series forward in time (positive lag uses past observations)."""
    if periods < 0:
        raise ValueError("periods must be non-negative")
    s = _as_series(values)
    return s.shift(periods)


def rolling_mean(values, window: int, *, min_periods: int | None = None) -> pd.Series:
    """Rolling mean with optional min_periods (defaults to window)."""
    if window <= 0:
        raise ValueError("window must be positive")
    s = _as_series(values)
    return s.rolling(window=window, min_periods=min_periods or window).mean()


def rolling_std(values, window: int, *, min_periods: int | None = None) -> pd.Series:
    """Rolling standard deviation."""
    if window <= 0:
        raise ValueError("window must be positive")
    s = _as_series(values)
    return s.rolling(window=window, min_periods=min_periods or window).std(ddof=1)


def rolling_zscore(values, window: int, *, min_periods: int | None = None) -> pd.Series:
    """Rolling z-score: (x - rolling_mean) / rolling_std."""
    mean = rolling_mean(values, window, min_periods=min_periods)
    std = rolling_std(values, window, min_periods=min_periods)
    s = _as_series(values)
    return (s - mean) / std
