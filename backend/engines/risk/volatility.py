"""Realized and EWMA volatility, regime classification, vol-based penalties."""
from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd

from quant_core.returns import _as_returns_series

VolatilityRegime = Literal["low", "normal", "elevated", "extreme", "unknown"]

PERIODS_PER_YEAR = 252
MIN_OBSERVATIONS = 20
DEFAULT_WINDOW = 21


def _clean_returns(returns) -> pd.Series:
    return _as_returns_series(returns).dropna()


def realized_volatility(
    returns,
    window: int,
    *,
    annualized: bool = True,
) -> float | None:
    """Sample standard deviation over the trailing `window` returns."""
    if window <= 1:
        raise ValueError("window must be > 1")
    r = _clean_returns(returns)
    if len(r) < window:
        return None
    vol = float(r.iloc[-window:].std(ddof=1))
    if annualized:
        vol *= float(np.sqrt(PERIODS_PER_YEAR))
    return vol


def ewma_volatility(
    returns,
    lambda_: float = 0.94,
    *,
    annualized: bool = True,
) -> float | None:
    """EWMA volatility (RiskMetrics-style variance recursion)."""
    if not 0.0 < lambda_ < 1.0:
        raise ValueError("lambda_ must be between 0 and 1")
    r = _clean_returns(returns)
    if len(r) < 2:
        return None
    var = float(r.iloc[0] ** 2)
    for ret in r.iloc[1:]:
        var = lambda_ * var + (1.0 - lambda_) * float(ret**2)
    vol = float(np.sqrt(max(var, 0.0)))
    if annualized:
        vol *= float(np.sqrt(PERIODS_PER_YEAR))
    return vol


def downside_volatility(
    returns,
    *,
    mar: float = 0.0,
    annualized: bool = True,
) -> float | None:
    """Standard deviation of returns below the minimum acceptable return (MAR)."""
    r = _clean_returns(returns)
    downside = r[r < mar]
    if len(downside) < 2:
        return None
    vol = float(downside.std(ddof=1))
    if annualized:
        vol *= float(np.sqrt(PERIODS_PER_YEAR))
    return vol


def _rolling_realized_vol_series(returns: pd.Series, window: int) -> list[float]:
    vals: list[float] = []
    for end in range(window, len(returns) + 1):
        chunk = returns.iloc[end - window : end]
        v = float(chunk.std(ddof=1)) * float(np.sqrt(PERIODS_PER_YEAR))
        vals.append(v)
    return vals


def volatility_regime(current_vol: float | None, rolling_vol_history: list[float]) -> VolatilityRegime:
    """Classify current vol vs historical rolling-vol distribution."""
    if current_vol is None or len(rolling_vol_history) < 5:
        return "unknown"
    hist = np.asarray(rolling_vol_history, dtype=float)
    p25, p75, p90 = np.percentile(hist, [25, 75, 90])
    if current_vol >= p90:
        return "extreme"
    if current_vol >= p75:
        return "elevated"
    if current_vol <= p25:
        return "low"
    return "normal"


def risk_penalty_from_volatility(vol_regime: VolatilityRegime, tail_risk: bool) -> float:
    """Map vol regime (+ optional tail flag) to score deduction points."""
    base = {
        "low": 0.0,
        "normal": 0.5,
        "elevated": 2.5,
        "extreme": 5.0,
        "unknown": 0.0,
    }
    penalty = float(base.get(vol_regime, 0.0))
    if tail_risk:
        penalty += 3.0
    return round(min(penalty, 10.0), 2)


def assess_volatility_risk(
    returns,
    *,
    window: int = DEFAULT_WINDOW,
    alpha: float = 0.05,
    lambda_: float = 0.94,
) -> dict[str, Any]:
    """
    Bundle vol, VaR/ES, regime, and penalty for RiskEngine v2.

    Returns JSON-serializable metrics; `sufficient_data=False` when history is too short.
    """
    from engines.risk.var_es import historical_expected_shortfall, historical_var, tail_risk_flag

    r = _clean_returns(returns)
    n = int(len(r))
    if n < MIN_OBSERVATIONS:
        return {
            "sufficient_data": False,
            "observations": n,
            "realized_volatility": None,
            "ewma_volatility": None,
            "downside_volatility": None,
            "historical_var": None,
            "historical_es": None,
            "volatility_regime": "unknown",
            "tail_risk": False,
            "risk_penalty_pts": 0.0,
            "window": window,
            "alpha": alpha,
        }

    realized = realized_volatility(r, window, annualized=True)
    ewma = ewma_volatility(r, lambda_, annualized=True)
    downside = downside_volatility(r, annualized=True)
    var = historical_var(r, alpha=alpha)
    es = historical_expected_shortfall(r, alpha=alpha)
    rolling_hist = _rolling_realized_vol_series(r, window)
    regime = volatility_regime(realized, rolling_hist)
    tail = tail_risk_flag(r, alpha=alpha, var=var, es=es)
    penalty = risk_penalty_from_volatility(regime, tail)

    return {
        "sufficient_data": True,
        "observations": n,
        "realized_volatility": round(realized, 6) if realized is not None else None,
        "ewma_volatility": round(ewma, 6) if ewma is not None else None,
        "downside_volatility": round(downside, 6) if downside is not None else None,
        "historical_var": round(var, 6) if var is not None else None,
        "historical_es": round(es, 6) if es is not None else None,
        "volatility_regime": regime,
        "tail_risk": tail,
        "risk_penalty_pts": penalty,
        "window": window,
        "alpha": alpha,
    }
