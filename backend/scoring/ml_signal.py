"""Optional ML-style signal for medium bucket (rule-based proxy of 20-day horizon)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scoring.technical import macd_score, momentum_score, relative_strength_vs_spy, trend_score


def ml_medium_horizon_score(stock_df: pd.DataFrame, spy_df: pd.DataFrame) -> float:
    """
    Phase 2 proxy: weighted technical features approximating a 20-day swing model
    without per-symbol trained pickles.
    """
    if len(stock_df) < 30:
        return 50.0

    mom20 = momentum_score(stock_df, days=20)
    trend = trend_score(stock_df)
    macd = macd_score(stock_df)
    rs = relative_strength_vs_spy(stock_df, spy_df, days=20)

    # Simple regression-like weights tuned for medium horizon
    score = mom20 * 0.30 + trend * 0.25 + macd * 0.20 + rs * 0.25

    # Volatility penalty for extreme moves
    returns = stock_df["close"].pct_change().dropna()
    if len(returns) >= 20:
        vol = returns.tail(20).std()
        if vol > 0.05:
            score -= 10
        elif vol < 0.015:
            score -= 5

    return float(np.clip(score, 0, 100))
