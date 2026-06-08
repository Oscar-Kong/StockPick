"""Long-term technical structure — support/resistance, MA, trend."""
from __future__ import annotations

import numpy as np
import pandas as pd
from ta.trend import SMAIndicator


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()
    w = df.set_index("date").resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    return w.reset_index()


def long_term_structure(df: pd.DataFrame) -> dict:
    """Support/resistance, 200d MA, weekly trend, volume flow."""
    if df is None or df.empty or len(df) < 60:
        return {}

    close = df["close"]
    price = float(close.iloc[-1])
    high_52 = float(df["high"].max())
    low_52 = float(df["low"].min())

    # Support / resistance from price distribution + recent swing
    support = float(df["low"].tail(120).quantile(0.15))
    resistance = float(df["high"].tail(120).quantile(0.85))
    major_support = float(low_52)
    major_resistance = float(high_52)

    ma200 = None
    ma200_position = "unknown"
    if len(df) >= 200:
        ma200 = float(SMAIndicator(close, window=200).sma_indicator().iloc[-1])
        if ma200 and ma200 > 0:
            pct = (price - ma200) / ma200
            if pct > 0.05:
                ma200_position = "above"
            elif pct < -0.05:
                ma200_position = "below"
            else:
                ma200_position = "near"

    weekly = resample_weekly(df)
    weekly_trend = "sideways"
    if len(weekly) >= 20:
        wma = float(weekly["close"].tail(20).mean())
        if price > wma * 1.03:
            weekly_trend = "bullish"
        elif price < wma * 0.97:
            weekly_trend = "bearish"

    monthly = df.set_index("date").resample("ME").agg({"close": "last"}).dropna()
    monthly_trend = "sideways"
    if len(monthly) >= 6:
        m6 = float(monthly["close"].iloc[-1])
        m6_ago = float(monthly["close"].iloc[-6])
        if m6_ago > 0:
            chg = (m6 - m6_ago) / m6_ago
            if chg > 0.08:
                monthly_trend = "bullish"
            elif chg < -0.08:
                monthly_trend = "bearish"

    vol_signal = "neutral"
    if len(df) >= 60:
        recent = float(df["volume"].tail(30).mean())
        prior = float(df["volume"].iloc[-60:-30].mean())
        near_low = price <= low_52 * 1.15
        near_high = price >= high_52 * 0.9
        if recent > prior * 1.2 and near_low:
            vol_signal = "accumulation_at_lows"
        elif recent > prior * 1.2 and near_high:
            vol_signal = "distribution_at_highs"
        elif recent < prior * 0.8:
            vol_signal = "drying_up"

    pct_in_range = (price - low_52) / (high_52 - low_52) if high_52 > low_52 else 0.5

    return {
        "price": round(price, 2),
        "high_52w": round(high_52, 2),
        "low_52w": round(low_52, 2),
        "pct_in_52w_range": round(pct_in_range * 100, 1),
        "support_near": round(support, 2),
        "resistance_near": round(resistance, 2),
        "major_support": round(major_support, 2),
        "major_resistance": round(major_resistance, 2),
        "ma200": round(ma200, 2) if ma200 else None,
        "ma200_position": ma200_position,
        "weekly_trend": weekly_trend,
        "monthly_trend": monthly_trend,
        "volume_signal": vol_signal,
    }


def fair_value_zones(
    price: float,
    low_52: float,
    high_52: float,
    pe: float | None,
    rev_growth: float | None,
) -> dict:
    """Undervalued / fair / overvalued zones from range and simple multiples."""
    if high_52 <= low_52:
        mid = price
        return {
            "undervalued_buy_zone": f"Below ${mid * 0.95:.2f} (estimate)",
            "fair_value_hold_zone": f"${mid * 0.95:.2f} – ${mid * 1.05:.2f}",
            "overvalued_reduce_zone": f"Above ${mid * 1.05:.2f} (estimate)",
            "current_zone": "fair",
        }

    range_pct = (price - low_52) / (high_52 - low_52)
    buy_top = low_52 + (high_52 - low_52) * 0.25
    fair_low = low_52 + (high_52 - low_52) * 0.35
    fair_high = low_52 + (high_52 - low_52) * 0.70
    sell_floor = low_52 + (high_52 - low_52) * 0.80

    current_zone = "fair"
    if range_pct <= 0.25 or (pe is not None and pe < 12 and pe > 0):
        current_zone = "undervalued"
    elif range_pct >= 0.80 or (pe is not None and pe > 45):
        current_zone = "overvalued"

    return {
        "undervalued_buy_zone": f"~${low_52:.2f} – ${buy_top:.2f} (lower quartile of 52w range)",
        "fair_value_hold_zone": f"~${fair_low:.2f} – ${fair_high:.2f}",
        "overvalued_reduce_zone": f"~${sell_floor:.2f} – ${high_52:.2f} (upper range / prior highs)",
        "current_zone": current_zone,
        "range_position_pct": round(range_pct * 100, 1),
    }
