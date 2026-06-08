"""Medium sleeve expanded factors (Phase 3)."""
from __future__ import annotations

import pandas as pd

from scoring.flow import cmf_score, large_block_volume_score, obv_slope_score
from scoring.metrics import clip100, safe_float
from scoring.technical import breakout_score, trend_score

try:
    from ta.trend import ADXIndicator
except ImportError:
    ADXIndicator = None


def trend_quality_score(df: pd.DataFrame) -> float:
    if df is None or df.empty or len(df) < 30:
        return 50.0
    trend = trend_score(df)
    adx_part = 50.0
    if ADXIndicator is not None and len(df) >= 20:
        adx = ADXIndicator(df["high"], df["low"], df["close"], window=14).adx().iloc[-1]
        if not pd.isna(adx):
            adx_part = clip100(float(adx), 15, 45)
    breakout = breakout_score(df)
    return (trend * 0.4 + adx_part * 0.35 + breakout * 0.25)


def earnings_revision_proxy(info: dict, fundamentals: dict) -> float:
    eps_g = safe_float(info.get("earningsGrowth"), default=0.0)
    rev_g = safe_float(info.get("revenueGrowth"), default=0.0)
    eps_est = safe_float(fundamentals.get("eps_estimate") or fundamentals.get("eps_growth_estimate"))
    score = 50.0
    if eps_g > 0.15:
        score += 25
    elif eps_g > 0.05:
        score += 12
    elif eps_g < -0.05:
        score -= 20
    if rev_g > 0.10:
        score += 10
    elif rev_g < 0:
        score -= 10
    if eps_est > eps_g and eps_est > 0:
        score += 8
    return max(0.0, min(100.0, score))


def holder_concentration_proxy(info: dict) -> float:
    """Insider/institutional ownership change proxy from available fields."""
    inst = safe_float(info.get("heldPercentInstitutions"))
    insider = safe_float(info.get("heldPercentInsiders"))
    if inst <= 0 and insider <= 0:
        return 50.0
    # Moderate insider + rising inst band preferred for swings
    score = 50.0
    if 0.4 <= inst <= 0.85:
        score += 15
    if 0.05 <= insider <= 0.25:
        score += 8
    if inst > 0.95:
        score -= 10
    return max(0.0, min(100.0, score))


def medium_expanded_scores(
    symbol: str,
    df: pd.DataFrame,
    info: dict,
    fundamentals: dict,
) -> dict[str, float]:
    del symbol
    return {
        "trend_quality": trend_quality_score(df),
        "obv_slope": obv_slope_score(df),
        "capital_flow": cmf_score(df),
        "institutional_buy": large_block_volume_score(df),
        "chip_concentration": holder_concentration_proxy(info),
        "earnings_revision": earnings_revision_proxy(info, fundamentals),
    }
