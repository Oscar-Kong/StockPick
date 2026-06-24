"""Build factor signals per sleeve — mirrors screeners/*.py score() signal legs."""
from __future__ import annotations

from config import OPENBB_ON_SCAN, SLEEVE_FACTORS_V3_ENABLED
from models.schemas import Bucket
from scoring.fundamental import (
    moat_proxy_score,
    revenue_eps_consistency_score,
    roic_margin_stability_score,
)
from scoring.technical import smooth_growth_score, smooth_growth_score_with_horizon
from data.fred_client import FredClient
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
from scoring.sector_strength import sector_relative_strength
from scoring.ml_signal import ml_medium_horizon_score
from screeners.base import CandidateContext, WeightedSignal
from screeners.penny import PennyScreener
from services.openbb_integration import append_governance_signal
from services.qlib_integration import get_symbol_alpha_score


def build_penny_signals(ctx: CandidateContext) -> list[WeightedSignal]:
    df = ctx.history
    sentiment_data = combined_sentiment_score(ctx.symbol, include_news=False)
    return [
        WeightedSignal("5-day momentum", momentum_score(df, 5), 0.25, "Recent price momentum"),
        WeightedSignal("Volume spike", volume_spike_score(df), 0.25, "Today vs 20-day average volume"),
        WeightedSignal("RSI fit", rsi_score(df), 0.15, "Not overbought"),
        WeightedSignal("Social buzz", sentiment_data["score"], 0.20, "StockTwits sentiment"),
        WeightedSignal("Volatility fit", volatility_fit_score(df), 0.15, "ATR-based tradeability"),
    ]


def build_medium_signals(ctx: CandidateContext) -> list[WeightedSignal]:
    df = ctx.history
    spy = ctx.spy_history
    if spy is None or getattr(spy, "empty", True):
        spy = PennyScreener()._spy()
    sentiment_data = combined_sentiment_score(ctx.symbol, include_news=True)
    rs = relative_strength_vs_spy(df, spy, days=20)
    technical = (macd_score(df) + breakout_score(df) + trend_score(df)) / 3
    ml_proxy = ml_medium_horizon_score(df, spy)
    qlib_signal, qlib_source = get_symbol_alpha_score(Bucket.medium, ctx.symbol, ml_proxy)
    sector = ctx.info.get("sector")
    sector_strength = sector_relative_strength(
        df, sector, spy, PennyScreener().ps.market, days=20
    )
    signals = [
        WeightedSignal("20d momentum vs SPY", rs, 0.22, "Relative strength vs benchmark"),
        WeightedSignal("Technical setup", technical, 0.23, "MACD, trend, breakout"),
        WeightedSignal("Sector RS vs SPY", sector_strength, 0.18, f"Stock vs {sector or 'sector'} ETF"),
        WeightedSignal("Qlib alpha (20d)", qlib_signal, 0.18, f"Model signal source: {qlib_source}"),
        WeightedSignal("Sentiment", sentiment_data["score"], 0.19, "Finnhub/StockTwits news"),
    ]
    return append_governance_signal(signals, ctx.symbol, allow_fetch=OPENBB_ON_SCAN)


def build_compounder_signals(ctx: CandidateContext) -> list[WeightedSignal]:
    df = ctx.history
    rev_eps = revenue_eps_consistency_score(ctx.info, ctx.fundamentals)
    roic = roic_margin_stability_score(ctx.info, ctx.fundamentals)
    smooth = (
        smooth_growth_score_with_horizon(df, years=5)
        if df is not None and not getattr(df, "empty", True)
        else smooth_growth_score_with_horizon(df, years=5)
    )
    moat = moat_proxy_score(ctx.info, ctx.fundamentals)
    macro = FredClient().macro_regime_score()
    qlib_fallback = (float(rev_eps) + float(roic) + smooth.score) / 3
    qlib_alpha, qlib_source = get_symbol_alpha_score(Bucket.compounder, ctx.symbol, qlib_fallback)
    signals = [
        WeightedSignal("Revenue/EPS consistency", float(rev_eps), 0.28, "Steady earnings and revenue growth"),
        WeightedSignal("ROIC & margins", float(roic), 0.24, "Profitability and balance sheet quality"),
        WeightedSignal(smooth.label, smooth.score, 0.20, "Low-volatility upward price trend"),
        WeightedSignal("Moat proxies", float(moat), 0.13, "Margins, FCF, sector quality"),
        WeightedSignal("Macro regime", macro, 0.10, "Economic backdrop for long holds"),
        WeightedSignal("Qlib alpha", qlib_alpha, 0.05, f"Model signal source: {qlib_source}"),
    ]
    return append_governance_signal(signals, ctx.symbol, allow_fetch=OPENBB_ON_SCAN)


_BUILDERS = {
    "penny": build_penny_signals,
    "medium": build_medium_signals,
    "compounder": build_compounder_signals,
}


def build_sleeve_signals(ctx: CandidateContext, sleeve: str) -> list[WeightedSignal]:
    if SLEEVE_FACTORS_V3_ENABLED:
        from engines.factor.sleeve_signals_v3 import (
            build_compounder_signals_v3,
            build_medium_signals_v3,
            build_penny_signals_v3,
        )

        v3_builders = {
            "penny": build_penny_signals_v3,
            "medium": build_medium_signals_v3,
            "compounder": build_compounder_signals_v3,
        }
        builder = v3_builders.get(sleeve)
        if builder:
            from engines.factor.openalpha_signals import append_openalpha_signals

            return append_openalpha_signals(sleeve, ctx, builder(ctx))
    builder = _BUILDERS.get(sleeve)
    if not builder:
        raise ValueError(f"Unknown sleeve: {sleeve}")
    from engines.factor.openalpha_signals import append_openalpha_signals

    return append_openalpha_signals(sleeve, ctx, builder(ctx))
