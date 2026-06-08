"""Historical factor score series for IC panel (maps factor_id → score)."""
from __future__ import annotations

import pandas as pd

from engines.factor.catalog import active_factor_catalog
from scoring.sentiment import combined_sentiment_score
from scoring.technical import (
    breakout_score,
    macd_score,
    momentum_score,
    relative_strength_vs_spy,
    rsi_score,
    trend_score,
    volatility_fit_score,
    volume_spike_score,
)


def factor_score_at_window(
    factor_id: str,
    hist: pd.DataFrame,
    spy: pd.DataFrame,
    *,
    symbol: str = "SPY",
) -> float | None:
    """Score factor using data through the last row of hist."""
    if hist is None or hist.empty or len(hist) < 30:
        return None

    sleeve = factor_id.split("_", 1)[0]
    key = factor_id[len(sleeve) + 1 :] if "_" in factor_id else factor_id

    try:
        from config import SLEEVE_FACTORS_V3_ENABLED

        if sleeve == "penny":
            if SLEEVE_FACTORS_V3_ENABLED:
                from scoring.penny_factors import penny_expanded_scores

                scores = penny_expanded_scores(symbol, hist, {}, {})
                if key in scores:
                    return scores[key]
            if key == "momentum_5d":
                return momentum_score(hist, 5)
            if key == "volume_spike":
                return volume_spike_score(hist)
            if key == "rsi_fit":
                return rsi_score(hist)
            if key in ("social_buzz", "social_sentiment"):
                return combined_sentiment_score(symbol, include_news=False)["score"]
            if key == "volatility_fit":
                return volatility_fit_score(hist)
            if key == "rel_volume":
                return volume_spike_score(hist)
            if key == "breakout_strength":
                from scoring.technical import breakout_score

                return breakout_score(hist)
        elif sleeve == "medium":
            spy_w = spy if spy is not None and not spy.empty else hist
            if SLEEVE_FACTORS_V3_ENABLED:
                from scoring.medium_factors import medium_expanded_scores

                scores = medium_expanded_scores(symbol, hist, {}, {})
                if key in scores:
                    return scores[key]
            if key == "rs_vs_spy":
                return relative_strength_vs_spy(hist, spy_w, days=20)
            if key == "technical_setup":
                return (macd_score(hist) + breakout_score(hist) + trend_score(hist)) / 3
            if key == "sector_rs":
                return relative_strength_vs_spy(hist, spy_w, days=20) * 0.95
            if key == "qlib_alpha":
                return momentum_score(hist, 20)
            if key == "sentiment":
                return combined_sentiment_score(symbol, include_news=True)["score"]
            if key == "governance":
                return 70.0
        elif sleeve == "compounder":
            if SLEEVE_FACTORS_V3_ENABLED:
                from scoring.compounder_v3 import compounder_expanded_scores

                scores = compounder_expanded_scores(hist, {}, {})
                if key in scores:
                    return scores[key]
                if key == "eps_growth":
                    return scores.get("adjusted_eps")
            if key in ("rev_eps", "roic_margins", "moat"):
                return trend_score(hist)
            if key == "smooth_growth":
                return trend_score(hist)
            if key == "macro_regime":
                return 55.0
            if key == "qlib_alpha":
                return momentum_score(hist, 20)
            if key == "governance":
                return 70.0
        if key.startswith("oa_"):
            from scoring.openalpha_factors import score_openalpha_factor

            fk = key[3:]
            return score_openalpha_factor(fk, hist, spy)
    except Exception:
        return None
    return None


def catalog_factor_ids(sleeve: str) -> list[str]:
    return [spec.factor_id for spec in active_factor_catalog().get(sleeve, [])]
