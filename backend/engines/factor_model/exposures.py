"""Return-matrix exposures: market beta and rolling correlation."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from quant_core.returns import simple_returns

MIN_OBS_BETA = 20
MIN_OBS_CORR = 10


def build_return_matrix(price_panel: pd.DataFrame) -> pd.DataFrame:
    """
    Align simple daily returns across symbols.

    ``price_panel`` columns are symbol tickers; index is datetime.
    """
    if price_panel is None or price_panel.empty:
        return pd.DataFrame()
    panel = price_panel.sort_index().astype(float).ffill()
    rets = panel.apply(simple_returns)
    return rets.dropna(how="any")


def estimate_market_betas(
    returns: pd.DataFrame,
    benchmark: str,
) -> dict[str, dict[str, float | None]]:
    """
    OLS market beta of each column vs benchmark (excluding benchmark itself).

    Returns per-symbol beta, alpha (daily), r_squared, and observation count.
    """
    bench = str(benchmark).upper()
    if bench not in returns.columns:
        raise ValueError(f"benchmark {bench} missing from return matrix")

    market = returns[bench].astype(float)
    out: dict[str, dict[str, float | None]] = {}

    for sym in returns.columns:
        if str(sym).upper() == bench:
            continue
        aligned = pd.concat([returns[sym], market], axis=1, join="inner").dropna()
        aligned.columns = ["asset", "market"]
        n = len(aligned)
        if n < MIN_OBS_BETA:
            out[str(sym).upper()] = {
                "beta": None,
                "alpha_daily": None,
                "r_squared": None,
                "observations": n,
                "sufficient": False,
            }
            continue

        y = aligned["asset"].to_numpy()
        x = aligned["market"].to_numpy()
        x_mean = float(x.mean())
        y_mean = float(y.mean())
        var_x = float(np.var(x, ddof=1))
        if var_x <= 0:
            beta = 0.0
        else:
            beta = float(np.cov(y, x, ddof=1)[0, 1] / var_x)
        alpha = y_mean - beta * x_mean

        preds = alpha + beta * x
        ss_res = float(np.sum((y - preds) ** 2))
        ss_tot = float(np.sum((y - y_mean) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        out[str(sym).upper()] = {
            "beta": round(beta, 4),
            "alpha_daily": round(alpha, 6),
            "r_squared": round(r2, 4),
            "observations": n,
            "sufficient": True,
        }

    return out


def rolling_correlation_matrix(
    returns: pd.DataFrame,
    window: int,
) -> dict[str, Any]:
    """
    Rolling Pearson correlation; returns the latest window matrix plus metadata.
    """
    if window <= 1:
        raise ValueError("window must be > 1")
    if returns is None or returns.empty:
        return {
            "window": window,
            "sufficient": False,
            "as_of": None,
            "matrix": {},
        }

    clean = returns.dropna(how="any")
    if len(clean) < MIN_OBS_CORR:
        return {
            "window": window,
            "sufficient": False,
            "as_of": None,
            "matrix": {},
            "observations": len(clean),
        }

    roll = clean.rolling(window=window, min_periods=min(window, MIN_OBS_CORR)).corr()
    if roll.empty:
        return {
            "window": window,
            "sufficient": False,
            "as_of": None,
            "matrix": {},
        }

    last_date = clean.index[-1]
    try:
        latest = roll.loc[last_date].copy()
    except KeyError:
        return {
            "window": window,
            "sufficient": False,
            "as_of": str(last_date),
            "matrix": {},
        }

    latest.index = [str(i).upper() for i in latest.index]
    latest.columns = [str(c).upper() for c in latest.columns]

    symbols = [str(c).upper() for c in clean.columns]
    matrix: dict[str, dict[str, float | None]] = {}
    for sym in symbols:
        row: dict[str, float | None] = {}
        for other in symbols:
            val = latest.loc[sym, other] if sym in latest.index and other in latest.columns else None
            if val is not None and not np.isnan(val):
                row[other] = round(float(val), 4)
            else:
                row[other] = None
        matrix[sym] = row

    return {
        "window": window,
        "sufficient": True,
        "as_of": str(last_date.date()) if hasattr(last_date, "date") else str(last_date),
        "observations": int(len(clean)),
        "matrix": matrix,
    }
