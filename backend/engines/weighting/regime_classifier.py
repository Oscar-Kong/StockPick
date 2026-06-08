"""Market regime classifier (5 regimes + neutral) from SPY features."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from data.price_service import PriceService

REGIMES = ("bull", "bear", "sideways", "high_vol", "low_vol", "neutral")

# Annualized vol thresholds (decimal)
_HIGH_VOL = 0.28
_LOW_VOL = 0.14
_BULL_VOL_CAP = 0.25
_R6M_BULL = 0.08
_R6M_BEAR = -0.08
_SLOPE_EPS = 0.0008  # daily slope on MA50 (~0.08% per day)


@dataclass
class RegimeFeatures:
    as_of_date: str
    price: float
    r6m: float
    sigma_20d_ann: float
    ma50: float
    ma200: float
    slope_50d: float
    above_ma200: bool


@dataclass
class RegimeResult:
    regime: str
    features: RegimeFeatures
    features_json: dict[str, Any]


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _features_from_spy(df: pd.DataFrame) -> RegimeFeatures | None:
    if df is None or df.empty or len(df) < 200:
        return None
    df = df.sort_values("date").reset_index(drop=True)
    close = df["close"].astype(float)
    as_of = str(df["date"].iloc[-1])[:10]
    price = float(close.iloc[-1])

    idx_6m = max(0, len(close) - 126)
    r6m = float(price / close.iloc[idx_6m] - 1.0) if close.iloc[idx_6m] > 0 else 0.0

    ret_20 = close.pct_change().tail(20).dropna()
    sigma = float(ret_20.std() * (252**0.5)) if len(ret_20) >= 5 else 0.20

    ma50 = float(close.tail(50).mean())
    ma200 = float(close.tail(200).mean())
    ma50_series = close.rolling(50).mean().dropna()
    slope_50d = 0.0
    if len(ma50_series) >= 10:
        y = ma50_series.tail(10).values
        x = list(range(len(y)))
        n = len(x)
        sx, sy = sum(x), sum(y)
        sxx = sum(i * i for i in x)
        sxy = sum(i * v for i, v in zip(x, y))
        denom = n * sxx - sx * sx
        slope_50d = (n * sxy - sx * sy) / denom if denom else 0.0

    return RegimeFeatures(
        as_of_date=as_of,
        price=price,
        r6m=round(r6m, 4),
        sigma_20d_ann=round(sigma, 4),
        ma50=round(ma50, 2),
        ma200=round(ma200, 2),
        slope_50d=round(slope_50d, 6),
        above_ma200=price > ma200,
    )


def classify_features(f: RegimeFeatures) -> str:
    """First-match priority: high vol → low vol → bear → bull → sideways → neutral."""
    if f.sigma_20d_ann >= _HIGH_VOL:
        return "high_vol"
    if f.sigma_20d_ann <= _LOW_VOL:
        return "low_vol"
    if f.r6m < _R6M_BEAR and not f.above_ma200:
        return "bear"
    if f.r6m > _R6M_BULL and f.above_ma200 and f.sigma_20d_ann < _BULL_VOL_CAP:
        return "bull"
    if abs(f.r6m) <= _R6M_BULL and abs(f.slope_50d) < _SLOPE_EPS:
        return "sideways"
    return "neutral"


def classify_spy(
    spy_df: pd.DataFrame | None = None,
    *,
    price_service: PriceService | None = None,
) -> RegimeResult | None:
    ps = price_service or PriceService()
    df = spy_df
    if df is None or getattr(df, "empty", True):
        df = ps.get_spy_history(period="1y")
    feats = _features_from_spy(df)
    if feats is None:
        return None
    regime = classify_features(feats)
    payload = {
        "as_of_date": feats.as_of_date,
        "price": feats.price,
        "r6m": feats.r6m,
        "sigma_20d_ann": feats.sigma_20d_ann,
        "ma50": feats.ma50,
        "ma200": feats.ma200,
        "slope_50d": feats.slope_50d,
        "above_ma200": feats.above_ma200,
        "regime": regime,
    }
    return RegimeResult(regime=regime, features=feats, features_json=payload)


def features_to_json(result: RegimeResult) -> str:
    return json.dumps(result.features_json)
