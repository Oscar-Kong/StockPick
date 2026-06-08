"""Return and risk metrics for price / return series."""
from __future__ import annotations

from typing import Union

import numpy as np
import pandas as pd

ArrayLike = Union[pd.Series, pd.DataFrame, np.ndarray, list[float]]


def _as_series(values: ArrayLike, *, name: str = "value") -> pd.Series:
    if isinstance(values, pd.Series):
        return values.astype(float)
    if isinstance(values, pd.DataFrame):
        if values.shape[1] != 1:
            raise ValueError("Expected a single-column DataFrame or Series")
        return values.iloc[:, 0].astype(float)
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError("Expected a one-dimensional array")
    return pd.Series(arr, name=name)


def _as_returns_series(values: ArrayLike) -> pd.Series:
    s = _as_series(values, name="return")
    return s.replace([np.inf, -np.inf], np.nan)


def simple_returns(prices: ArrayLike) -> pd.Series:
    """Period-over-period simple returns: p_t / p_{t-1} - 1."""
    p = _as_series(prices, name="price")
    return p.pct_change()


def log_returns(prices: ArrayLike) -> pd.Series:
    """Period-over-period log returns: log(p_t / p_{t-1})."""
    p = _as_series(prices, name="price")
    shifted = p.shift(1)
    out = np.log(p / shifted)
    return pd.Series(out, index=p.index, name="log_return")


def cumulative_simple_return(returns: ArrayLike) -> pd.Series:
    """Cumulative simple return path from a return series."""
    r = _as_returns_series(returns)
    return (1.0 + r).cumprod() - 1.0


def rolling_return(prices: ArrayLike, window: int) -> pd.Series:
    """Simple return over a rolling lookback window: p_t / p_{t-window} - 1."""
    if window <= 0:
        raise ValueError("window must be positive")
    p = _as_series(prices, name="price")
    return p / p.shift(window) - 1.0


def excess_returns(asset_returns: ArrayLike, benchmark_returns: ArrayLike) -> pd.Series:
    """Asset returns minus benchmark returns on aligned observations."""
    asset = _as_returns_series(asset_returns)
    bench = _as_returns_series(benchmark_returns)
    aligned = pd.concat([asset, bench], axis=1, join="inner")
    aligned.columns = ["asset", "benchmark"]
    out = aligned["asset"] - aligned["benchmark"]
    out.name = "excess_return"
    return out


def annualized_return(returns: ArrayLike, periods_per_year: int = 252) -> float:
    """Geometric annualized return from per-period simple returns."""
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    r = _as_returns_series(returns).dropna()
    if r.empty:
        return 0.0
    total = float((1.0 + r).prod())
    periods = len(r)
    if total <= 0:
        return 0.0
    return float(total ** (periods_per_year / periods) - 1.0)


def annualized_volatility(returns: ArrayLike, periods_per_year: int = 252) -> float:
    """Annualized volatility from per-period simple returns."""
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    r = _as_returns_series(returns).dropna()
    if len(r) < 2:
        return 0.0
    return float(r.std(ddof=1) * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: ArrayLike) -> float:
    """
    Maximum drawdown as a negative fraction (e.g. -0.15 for a 15% peak-to-trough drop).
    """
    eq = _as_series(equity_curve, name="equity").dropna()
    if eq.empty:
        return 0.0
    peak = eq.cummax()
    drawdown = (eq - peak) / peak
    return float(drawdown.min())
