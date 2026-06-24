"""Penny sleeve expanded factors (Phase 3)."""
from __future__ import annotations

import pandas as pd

from data.price_service import avg_dollar_volume_from_history
from scoring.metrics import clip100, safe_float
from scoring.sentiment import sentiment_polarity_scores
from scoring.technical import breakout_score, volatility_fit_score, volume_spike_score


def rel_volume_score(df: pd.DataFrame, lookback: int = 20) -> float:
    from scoring.penny_liquidity import (
        relative_volume_ratio_from_df,
        relative_volume_score_from_ratio,
    )

    ratio = relative_volume_ratio_from_df(df, lookback=lookback)
    return relative_volume_score_from_ratio(ratio)


def volume_surge_zscore(df: pd.DataFrame, lookback: int = 20) -> float:
    if df is None or df.empty or len(df) < lookback + 2:
        return 50.0
    vol = df["volume"].iloc[-lookback:]
    mu = vol.iloc[:-1].mean()
    sigma = vol.iloc[:-1].std()
    latest = vol.iloc[-1]
    if sigma <= 0 or mu <= 0:
        return volume_spike_score(df, lookback)
    z = (latest - mu) / sigma
    return clip100(z, -1.0, 3.0)


def intraday_vol_score(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 50.0
    row = df.iloc[-1]
    close = safe_float(row.get("close"))
    high = safe_float(row.get("high"))
    low = safe_float(row.get("low"))
    if close <= 0:
        return 50.0
    range_pct = (high - low) / close
    return clip100(range_pct, 0.02, 0.12)


def limit_up_proxy_score(df: pd.DataFrame, window: int = 20) -> float:
    """US proxy: gap up >3% with volume >1.5× 20d avg."""
    if df is None or df.empty or len(df) < window + 2:
        return 0.0
    hits = 0
    for i in range(-window, 0):
        prev_close = safe_float(df["close"].iloc[i - 1])
        open_p = safe_float(df["open"].iloc[i])
        vol = safe_float(df["volume"].iloc[i])
        avg_v = df["volume"].iloc[max(0, i - 21) : i].mean()
        if prev_close <= 0:
            continue
        gap = (open_p / prev_close) - 1.0
        if gap >= 0.03 and avg_v > 0 and vol >= 1.5 * avg_v:
            hits += 1
    return clip100(hits, 0, 4)


def float_size_score(info: dict, fundamentals: dict) -> float:
    """Smaller float → higher score for penny momentum (inverted cap rank)."""
    shares = safe_float(info.get("sharesOutstanding") or info.get("floatShares"))
    if shares <= 0:
        shares = safe_float(fundamentals.get("shares_outstanding"))
    mcap = safe_float(info.get("marketCap") or fundamentals.get("market_cap"))
    price = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    if shares <= 0 and mcap > 0 and price > 0:
        shares = mcap / price
    if shares <= 0:
        return 50.0
    if shares <= 20_000_000:
        return 90.0
    if shares <= 50_000_000:
        return 75.0
    if shares <= 100_000_000:
        return 55.0
    if shares <= 300_000_000:
        return 35.0
    return 20.0


def liquidity_score(df: pd.DataFrame) -> float:
    dv = avg_dollar_volume_from_history(df)
    return clip100(dv, 500_000, 5_000_000)


def penny_expanded_scores(
    symbol: str,
    df: pd.DataFrame,
    info: dict,
    fundamentals: dict,
) -> dict[str, float]:
    pol = sentiment_polarity_scores(symbol)
    return {
        "rel_volume": rel_volume_score(df),
        "volume_surge": volume_surge_zscore(df),
        "breakout_strength": breakout_score(df),
        "social_sentiment": pol["combined"],
        "sentiment_pos": pol["positive"],
        "sentiment_neg": pol["negative"],
        "intraday_vol": intraday_vol_score(df),
        "limit_up_freq": limit_up_proxy_score(df),
        "float_size": float_size_score(info, fundamentals),
        "liquidity": liquidity_score(df),
        "volatility_fit": volatility_fit_score(df),
    }
