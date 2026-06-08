"""US-adapted factor scores inspired by OpenAlpha formula patterns (0–100 scale)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from engines.factor.operators import (
    cs_rank,
    ensure_vwap,
    ts_correlation,
    ts_delay,
    ts_mean,
    ts_ols,
    ts_ret,
    ts_std,
)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return 50.0
    return max(lo, min(hi, float(value)))


def _z_to_score(z: float, scale: float = 2.0) -> float:
    return _clamp(50 + z * scale * 10)


def vwap_close_gap_score(df: pd.DataFrame, window: int = 5) -> float:
    """OpenAlpha 5000001: ts_mean(vwap - close, d)."""
    if len(df) < window + 2:
        return 50.0
    vwap = ensure_vwap(df)
    gap = ts_mean(vwap - df["close"], window)
    z = ts_mean(gap, max(window * 4, 20)).iloc[-1]
    if pd.isna(z):
        return 50.0
    std = gap.rolling(max(window * 4, 20)).std().iloc[-1]
    if pd.isna(std) or std <= 1e-9:
        return 50.0
    return _z_to_score(float(gap.iloc[-1] / std))


def ols_price_residual_score(df: pd.DataFrame, window: int = 10) -> float:
    """OpenAlpha 5000006: -ts_ols(close, ret1, d)[2] — mean-reversion tilt."""
    if len(df) < window + 5:
        return 50.0
    ret1 = ts_ret(df["close"], 1)
    _, _, resid = ts_ols(df["close"], ret1, window)
    r = resid.iloc[-1]
    if pd.isna(r):
        return 50.0
    std = resid.dropna().tail(window * 3).std()
    if pd.isna(std) or std <= 1e-9:
        return 50.0
    return _z_to_score(float(-r / std))


def volume_return_corr_score(df: pd.DataFrame, window: int = 5) -> float:
    """OpenAlpha 5000010: ts_correlation(cs_rank(volume), cs_rank(ret1), d)."""
    if len(df) < window + 10:
        return 50.0
    ret1 = ts_ret(df["close"], 1)
    vol_rank = ts_delay(df["volume"], 1)
    corr = ts_correlation(cs_rank(vol_rank), cs_rank(ret1), window)
    c = corr.iloc[-1]
    if pd.isna(c):
        return 50.0
    return _clamp(50 + c * 50)


def spy_return_corr_score(df: pd.DataFrame, spy: pd.DataFrame, window: int = 20) -> float:
    """OpenAlpha 5000012: ts_correlation(ret1, benchmark_ret1, d)."""
    if len(df) < window + 5 or spy is None or spy.empty:
        return 50.0
    spy = spy.reset_index(drop=True)
    hist = df.reset_index(drop=True)
    n = min(len(hist), len(spy))
    if n < window + 5:
        return 50.0
    ret = ts_ret(hist["close"].iloc[-n:], 1)
    spy_ret = ts_ret(spy["close"].iloc[-n:], 1)
    corr = ts_correlation(ret, spy_ret, window)
    c = corr.iloc[-1]
    if pd.isna(c):
        return 50.0
    return _clamp(50 + c * 40)


def return_autocorr_score(df: pd.DataFrame, window: int = 20) -> float:
    """OpenAlpha 5000014: ts_ols(ret1, ts_delay(ret1,1), d)[0] — momentum persistence."""
    if len(df) < window + 5:
        return 50.0
    ret1 = ts_ret(df["close"], 1)
    lag = ts_delay(ret1, 1)
    alpha, _, _ = ts_ols(ret1, lag, window)
    a = alpha.iloc[-1]
    if pd.isna(a):
        return 50.0
    return _z_to_score(float(a * 500), scale=1.5)


def vol_asymmetry_score(df: pd.DataFrame, window: int = 100) -> float:
    """OpenAlpha 5000024: ts_std(low/close-1) - ts_std(high/close-1)."""
    if len(df) < min(window, 60) + 5:
        window = min(window, max(20, len(df) // 2))
    if len(df) < 25:
        return 50.0
    prev = ts_delay(df["close"], 1).replace(0, np.nan)
    low_ret = df["low"] / prev - 1
    high_ret = df["high"] / prev - 1
    spread = ts_std(low_ret, window) - ts_std(high_ret, window)
    s = spread.iloc[-1]
    if pd.isna(s):
        return 50.0
    hist = spread.dropna().tail(window)
    if len(hist) < 10:
        return 50.0
    std = hist.std()
    if pd.isna(std) or std <= 1e-9:
        return 50.0
    return _z_to_score(float(s / std))


OPENALPHA_SCORERS: dict[str, object] = {
    "vwap_close_gap": vwap_close_gap_score,
    "ols_price_residual": ols_price_residual_score,
    "vol_ret_corr": volume_return_corr_score,
    "spy_corr_20d": spy_return_corr_score,
    "ret_autocorr": return_autocorr_score,
    "vol_asymmetry": vol_asymmetry_score,
}


def score_openalpha_factor(
    factor_key: str,
    hist: pd.DataFrame,
    spy: pd.DataFrame | None = None,
) -> float | None:
    fn = OPENALPHA_SCORERS.get(factor_key)
    if fn is None:
        return None
    try:
        if factor_key == "spy_corr_20d":
            return float(fn(hist, spy))  # type: ignore[operator]
        return float(fn(hist))  # type: ignore[operator]
    except Exception:
        return None
