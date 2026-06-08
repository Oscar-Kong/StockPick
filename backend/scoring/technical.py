"""Technical indicator scoring."""
from __future__ import annotations

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, MACD, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands


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
    if len(df) < lookback + 1:
        return 0.0
    avg_vol = df["volume"].iloc[-lookback - 1 : -1].mean()
    latest = df["volume"].iloc[-1]
    if avg_vol <= 0:
        return 0.0
    ratio = latest / avg_vol
    return _clamp(min(ratio, 3.0) / 3.0 * 100)


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
    if len(df) < 252:
        return 50.0
    window = df.tail(min(len(df), 252 * years))
    closes = window["close"].values
    if len(closes) < 50:
        return 50.0
    total_return = closes[-1] / closes[0] - 1
    if total_return <= 0:
        return max(0.0, 20 + total_return * 100)
    log_returns = np.diff(np.log(closes))
    volatility = np.std(log_returns) * np.sqrt(252)
    # Reward growth with low volatility (smooth compounders)
    if volatility <= 0:
        return 50.0
    sharpe_like = total_return / volatility
    return _clamp(40 + sharpe_like * 30 + total_return * 50)


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
