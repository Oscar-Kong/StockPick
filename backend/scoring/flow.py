"""Volume flow factors — OBV slope, Chaikin money flow (Phase 3 medium sleeve)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scoring.metrics import clip100


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def obv_slope_score(df: pd.DataFrame, window: int = 20) -> float:
    if df is None or df.empty or len(df) < window + 5:
        return 50.0
    close = df["close"].astype(float)
    vol = df["volume"].astype(float)
    direction = np.sign(close.diff().fillna(0))
    obv = (direction * vol).cumsum()
    y = obv.iloc[-window:].values
    x = np.arange(len(y), dtype=float)
    if len(y) < 5:
        return 50.0
    slope = np.polyfit(x, y, 1)[0]
    norm = obv.iloc[-window:].std() or 1.0
    z = slope / norm
    return _clamp(50 + z * 25)


def cmf_score(df: pd.DataFrame, window: int = 20) -> float:
    if df is None or df.empty or len(df) < window + 2:
        return 50.0
    try:
        from ta.volume import ChaikinMoneyFlowIndicator

        cmf = ChaikinMoneyFlowIndicator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            volume=df["volume"],
            window=window,
        ).chaikin_money_flow().iloc[-1]
        if pd.isna(cmf):
            return 50.0
        return clip100(float(cmf), -0.25, 0.25)
    except Exception:
        return _manual_cmf(df, window)


def _manual_cmf(df: pd.DataFrame, window: int) -> float:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    vol = df["volume"].astype(float)
    denom = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / denom
    mfv = mfm * vol
    tail = mfv.iloc[-window:]
    vtail = vol.iloc[-window:]
    if vtail.sum() <= 0:
        return 50.0
    cmf = tail.sum() / vtail.sum()
    return clip100(float(cmf), -0.25, 0.25)


def large_block_volume_score(df: pd.DataFrame, window: int = 20) -> float:
    """Institutional flow proxy: share of volume on high-range days."""
    if df is None or df.empty or len(df) < window:
        return 50.0
    tail = df.iloc[-window:]
    ranges = (tail["high"] - tail["low"]) / tail["close"].replace(0, np.nan)
    vol = tail["volume"]
    threshold = ranges.quantile(0.75)
    mask = ranges >= threshold
    if vol.sum() <= 0:
        return 50.0
    ratio = vol[mask].sum() / vol.sum()
    return clip100(ratio, 0.15, 0.55)
