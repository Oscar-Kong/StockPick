"""Market regime overlays — volatility and sector tilt for scan scoring."""
from __future__ import annotations

from typing import Any

import pandas as pd

from config import REGIME_OVERLAY_ENABLED
from data.market_data_client import MarketDataClient
from scoring.sector_strength import sector_relative_strength
from scoring.technical import volatility_fit_score


def spy_volatility_regime(spy_df: pd.DataFrame | None = None) -> dict[str, Any]:
    """
    Classify SPY volatility regime from ATR% on recent history.
    Returns multiplier in [0.85, 1.15] for scan scores.
    """
    if not REGIME_OVERLAY_ENABLED:
        return {"regime": "neutral", "multiplier": 1.0, "enabled": False}

    df = spy_df
    if df is None or df.empty:
        market = MarketDataClient()
        df = market.get_history("SPY", period="6mo")
    if df is None or df.empty or len(df) < 30:
        return {"regime": "unknown", "multiplier": 1.0, "enabled": True}

    vol_score = volatility_fit_score(df)
    if vol_score >= 75:
        return {"regime": "low_vol", "multiplier": 1.08, "enabled": True, "vol_score": vol_score}
    if vol_score <= 40:
        return {"regime": "high_vol", "multiplier": 0.90, "enabled": True, "vol_score": vol_score}
    return {"regime": "neutral", "multiplier": 1.0, "enabled": True, "vol_score": vol_score}


def sector_regime_tilt(
    sector: str | None,
    stock_df: pd.DataFrame | None = None,
    spy_df: pd.DataFrame | None = None,
    market: MarketDataClient | None = None,
) -> dict[str, Any]:
    """Tilt score when symbol sector ETF shows relative strength."""
    if not REGIME_OVERLAY_ENABLED or not sector:
        return {"tilt": 0.0, "enabled": False}

    if stock_df is None or stock_df.empty or spy_df is None or spy_df.empty:
        return {"tilt": 0.0, "enabled": True}

    market = market or MarketDataClient()
    rs = sector_relative_strength(stock_df, sector, spy_df, market=market)
    # Map RS score ~50-100 to tilt -5..+8 points
    tilt = (rs - 50) * 0.16
    return {"tilt": round(max(-5.0, min(8.0, tilt)), 2), "sector_rs": rs, "enabled": True}


def apply_regime_to_score(
    score: float,
    bucket: str,
    *,
    sector: str | None = None,
    stock_df: pd.DataFrame | None = None,
    spy_df: pd.DataFrame | None = None,
) -> tuple[float, dict[str, Any]]:
    """Apply vol + sector overlays; penny bucket dampened more in high vol."""
    meta: dict[str, Any] = {"bucket": bucket}
    if not REGIME_OVERLAY_ENABLED:
        return score, meta

    vol = spy_volatility_regime(spy_df)
    mult = float(vol["multiplier"])
    if bucket == "penny" and vol["regime"] == "high_vol":
        mult = min(mult, 0.88)
    elif bucket == "compounder" and vol["regime"] == "low_vol":
        mult = max(mult, 1.05)

    adjusted = score * mult
    sector_meta = sector_regime_tilt(sector, stock_df=stock_df, spy_df=spy_df)
    adjusted += float(sector_meta.get("tilt") or 0)
    adjusted = max(0.0, min(100.0, adjusted))

    meta["vol_regime"] = vol
    meta["sector_regime"] = sector_meta
    meta["final_multiplier"] = round(mult, 3)
    return round(adjusted, 2), meta
