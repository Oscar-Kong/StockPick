"""Pandas/numpy operators inspired by WorldQuant / OpenAlpha expression DSL."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ts_delay(series: pd.Series, d: int) -> pd.Series:
    return series.shift(d)


def ts_mean(series: pd.Series, d: int) -> pd.Series:
    return series.rolling(d, min_periods=max(1, d // 2)).mean()


def ts_std(series: pd.Series, d: int) -> pd.Series:
    return series.rolling(d, min_periods=max(1, d // 2)).std()


def ts_sum(series: pd.Series, d: int) -> pd.Series:
    return series.rolling(d, min_periods=max(1, d // 2)).sum()


def ts_rank(series: pd.Series, d: int) -> pd.Series:
    return series.rolling(d, min_periods=max(1, d // 2)).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) else np.nan,
        raw=False,
    )


def ts_zscore(series: pd.Series, d: int) -> pd.Series:
    m = ts_mean(series, d)
    s = ts_std(series, d)
    return (series - m) / s.replace(0, np.nan)


def ts_ret(series: pd.Series, d: int = 1) -> pd.Series:
    return series.pct_change(d)


def ts_correlation(x: pd.Series, y: pd.Series, d: int) -> pd.Series:
    return x.rolling(d, min_periods=max(3, d // 2)).corr(y)


def ts_ols(y: pd.Series, x: pd.Series, d: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Rolling OLS: returns (alpha, beta, residual at t)."""

    def _fit(window_y: np.ndarray, window_x: np.ndarray) -> tuple[float, float, float]:
        if len(window_y) < 3 or np.any(np.isnan(window_y)) or np.any(np.isnan(window_x)):
            return np.nan, np.nan, np.nan
        x = window_x.astype(float)
        y = window_y.astype(float)
        x_mean = x.mean()
        y_mean = y.mean()
        denom = ((x - x_mean) ** 2).sum()
        if denom <= 1e-12:
            return np.nan, np.nan, np.nan
        beta = ((x - x_mean) * (y - y_mean)).sum() / denom
        alpha = y_mean - beta * x_mean
        resid = y[-1] - (alpha + beta * x[-1])
        return alpha, beta, resid

    alphas: list[float] = []
    betas: list[float] = []
    resids: list[float] = []
    yv = y.values
    xv = x.values
    for i in range(len(y)):
        if i + 1 < d:
            alphas.append(np.nan)
            betas.append(np.nan)
            resids.append(np.nan)
            continue
        a, b, r = _fit(yv[i - d + 1 : i + 1], xv[i - d + 1 : i + 1])
        alphas.append(a)
        betas.append(b)
        resids.append(r)
    idx = y.index
    return (
        pd.Series(alphas, index=idx),
        pd.Series(betas, index=idx),
        pd.Series(resids, index=idx),
    )


def cs_rank(values: pd.Series) -> pd.Series:
    return values.rank(pct=True)


def cs_industry_neutral(values: pd.Series, groups: pd.Series) -> pd.Series:
    """Demean within group (sector)."""
    out = values.astype(float).copy()
    for _, idx in values.groupby(groups).groups.items():
        block = out.loc[list(idx)]
        out.loc[list(idx)] = block - block.mean()
    return out


def ensure_vwap(df: pd.DataFrame) -> pd.Series:
    if "vwap" in df.columns and df["vwap"].notna().any():
        return df["vwap"].astype(float)
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan)
    cum_tp_vol = (typical * vol).cumsum()
    cum_vol = vol.cumsum()
    vwap = cum_tp_vol / cum_vol
    return vwap.fillna(df["close"])
