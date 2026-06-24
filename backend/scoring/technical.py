"""Technical indicator scoring."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, MACD, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands


@dataclass(frozen=True)
class SmoothGrowthResult:
    score: float
    label: str
    bars_used: int
    years_requested: int
    years_effective: float


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def momentum_score(df: pd.DataFrame, days: int = 5) -> float:
    if len(df) < days + 1:
        return 0.0
    start = df["close"].iloc[-days - 1]
    end = df["close"].iloc[-1]
    if start <= 0:
        return 0.0
    ret = (end - start) / start
    return _clamp(50 + ret * 500)


def volume_spike_score(df: pd.DataFrame, lookback: int = 20) -> float:
    from scoring.penny_liquidity import (
        relative_volume_ratio_from_df,
        relative_volume_score_from_ratio,
    )

    ratio = relative_volume_ratio_from_df(df, lookback=lookback)
    return relative_volume_score_from_ratio(ratio)


def rsi_score(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period + 5:
        return 50.0
    rsi = RSIIndicator(df["close"], window=period).rsi().iloc[-1]
    if pd.isna(rsi):
        return 50.0
    # Prefer 40-60 for penny, penalize overbought >70
    if rsi > 70:
        return _clamp(100 - (rsi - 70) * 3)
    if rsi < 30:
        return _clamp(30 + rsi)
    return _clamp(50 + (50 - abs(rsi - 50)) * 0.5)


def macd_score(df: pd.DataFrame) -> float:
    if len(df) < 35:
        return 50.0
    macd = MACD(df["close"])
    hist = macd.macd_diff().iloc[-1]
    if pd.isna(hist):
        return 50.0
    return _clamp(50 + hist * 20)


def trend_score(df: pd.DataFrame) -> float:
    if len(df) < 55:
        return 50.0
    sma50 = SMAIndicator(df["close"], window=50).sma_indicator().iloc[-1]
    price = df["close"].iloc[-1]
    if pd.isna(sma50) or sma50 <= 0:
        return 50.0
    above = price > sma50
    distance = (price - sma50) / sma50
    base = 70 if above else 30
    return _clamp(base + distance * 200)


def breakout_score(df: pd.DataFrame, lookback: int = 20) -> float:
    if len(df) < lookback + 1:
        return 50.0
    window = df.iloc[-lookback - 1 : -1]
    high = window["high"].max()
    low = window["low"].min()
    price = df["close"].iloc[-1]
    if high <= low:
        return 50.0
    if price >= high:
        return 85.0
    if price <= low:
        return 25.0
    position = (price - low) / (high - low)
    return _clamp(position * 100)


def relative_strength_vs_spy(stock_df: pd.DataFrame, spy_df: pd.DataFrame, days: int = 20) -> float:
    if len(stock_df) < days + 1 or len(spy_df) < days + 1:
        return 50.0
    s_ret = stock_df["close"].iloc[-1] / stock_df["close"].iloc[-days - 1] - 1
    spy_ret = spy_df["close"].iloc[-1] / spy_df["close"].iloc[-days - 1] - 1
    diff = s_ret - spy_ret
    return _clamp(50 + diff * 400)


def atr_percent(df: pd.DataFrame, window: int = 14) -> float:
    """Latest ATR as % of price (annualized scale not applied)."""
    if df is None or df.empty or len(df) < window + 2:
        return 5.0
    atr = AverageTrueRange(df["high"], df["low"], df["close"], window=window).average_true_range().iloc[-1]
    price = df["close"].iloc[-1]
    if pd.isna(atr) or price <= 0:
        return 5.0
    return float(atr / price * 100)


def volatility_fit_score(df: pd.DataFrame) -> float:
    if len(df) < 20:
        return 50.0
    atr = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range().iloc[-1]
    price = df["close"].iloc[-1]
    if pd.isna(atr) or price <= 0:
        return 50.0
    atr_pct = atr / price
    # Sweet spot ~3-8% daily range for penny momentum
    if 0.03 <= atr_pct <= 0.08:
        return 85.0
    if atr_pct < 0.02:
        return 40.0
    if atr_pct > 0.12:
        return 35.0
    return 60.0


def smooth_growth_score(df: pd.DataFrame, years: int = 5) -> float:
    """Score smooth upward price trend over ~5 years."""
    return smooth_growth_score_with_horizon(df, years=years).score


def smooth_growth_score_with_horizon(df: pd.DataFrame, years: int = 5) -> SmoothGrowthResult:
    """Score smooth upward trend; label reflects the actual history window used."""
    if df is None or df.empty or len(df) < 252:
        effective = len(df) / 252.0 if df is not None and len(df) else 0.0
        label = f"{effective:.1f}Y smooth growth (insufficient history)"
        return SmoothGrowthResult(50.0, label, len(df) if df is not None else 0, years, round(effective, 2))

    bars_requested = 252 * years
    window = df.tail(min(len(df), bars_requested))
    closes = window["close"].values
    bars_used = len(closes)
    years_effective = round(bars_used / 252.0, 2)
    if years_effective >= years - 0.25:
        label = f"{years}Y smooth growth"
    else:
        label = f"{years_effective:.1f}Y smooth growth"

    if bars_used < 50:
        return SmoothGrowthResult(50.0, f"{label} (insufficient history)", bars_used, years, years_effective)

    total_return = closes[-1] / closes[0] - 1
    if total_return <= 0:
        return SmoothGrowthResult(
            max(0.0, 20 + total_return * 100),
            label,
            bars_used,
            years,
            years_effective,
        )
    log_returns = np.diff(np.log(closes))
    volatility = np.std(log_returns) * np.sqrt(252)
    if volatility <= 0:
        return SmoothGrowthResult(50.0, label, bars_used, years, years_effective)
    sharpe_like = total_return / volatility
    score = _clamp(40 + sharpe_like * 30 + total_return * 50)
    return SmoothGrowthResult(score, label, bars_used, years, years_effective)


def adx_score(df: pd.DataFrame, period: int = 14) -> float:
    """Trend strength via ADX — higher = stronger directional move."""
    if len(df) < period + 10:
        return 50.0
    adx = ADXIndicator(df["high"], df["low"], df["close"], window=period).adx().iloc[-1]
    if pd.isna(adx):
        return 50.0
    if adx >= 30:
        return _clamp(70 + (adx - 30))
    if adx >= 20:
        return _clamp(45 + (adx - 20) * 2.5)
    return _clamp(adx * 2)


def macd_rsi_confluence_score(df: pd.DataFrame) -> float:
    """MACD histogram rising + RSI in constructive zone (40–70)."""
    if len(df) < 35:
        return 50.0
    macd = MACD(df["close"])
    hist = macd.macd_diff()
    if len(hist) < 3:
        return 50.0
    rising = hist.iloc[-1] > hist.iloc[-2] > 0
    rsi = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
    if pd.isna(rsi):
        return 50.0
    rsi_ok = 40 <= rsi <= 70
    base = 50.0
    if rising:
        base += 25
    if rsi_ok:
        base += 20
    return _clamp(base)


def bollinger_lower_touch_score(df: pd.DataFrame, window: int = 20) -> float:
    """Mean-reversion setup: price near or below lower Bollinger band."""
    if len(df) < window + 5:
        return 50.0
    bb = BollingerBands(df["close"], window=window)
    lower = bb.bollinger_lband().iloc[-1]
    upper = bb.bollinger_hband().iloc[-1]
    price = df["close"].iloc[-1]
    if pd.isna(lower) or pd.isna(upper) or upper <= lower:
        return 50.0
    if price <= lower:
        return 85.0
    position = (price - lower) / (upper - lower)
    if position <= 0.15:
        return 75.0
    return _clamp(50 - position * 30)


def golden_cross_score(df: pd.DataFrame) -> float:
    """SMA50 above SMA200 with positive separation."""
    if len(df) < 205:
        return 50.0
    sma50 = SMAIndicator(df["close"], window=50).sma_indicator().iloc[-1]
    sma200 = SMAIndicator(df["close"], window=200).sma_indicator().iloc[-1]
    if pd.isna(sma50) or pd.isna(sma200) or sma200 <= 0:
        return 50.0
    if sma50 > sma200:
        spread = (sma50 - sma200) / sma200
        return _clamp(65 + spread * 400)
    return _clamp(35 + (sma50 / sma200 - 1) * 100)


def pct_from_52w_high_score(df: pd.DataFrame) -> float:
    """Higher when closer to 52-week high (breakout proximity)."""
    if len(df) < 60:
        return 50.0
    window = df.tail(min(len(df), 252))
    high_52 = window["high"].max()
    price = df["close"].iloc[-1]
    if high_52 <= 0:
        return 50.0
    pct = price / high_52
    return _clamp(pct * 100)


def spread_proxy_score(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    row = df.iloc[-1]
    if row["close"] <= 0:
        return 0.0
    spread = (row["high"] - row["low"]) / row["close"]
    if spread > 0.15:
        return 20.0
    if spread > 0.10:
        return 50.0
    return 80.0
