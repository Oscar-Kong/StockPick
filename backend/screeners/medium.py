"""Medium-term swing screener — 1-2 month holds."""
from __future__ import annotations

from config import (
    MEDIUM_MARKET_CAP_MAX,
    MEDIUM_MARKET_CAP_MIN,
    MEDIUM_MIN_DOLLAR_VOLUME_20D,
    MEDIUM_MIN_VOLUME,
    MEDIUM_PRICE_MAX,
    MEDIUM_PRICE_MIN,
)
from data.candidate_builder import build_candidate
from data.price_service import (
    PriceService,
    avg_dollar_volume_from_history,
    avg_volume_from_history,
)
from models.schemas import Bucket, RiskLevel, ScanOptions
from scoring.ml_signal import ml_medium_horizon_score
from scoring.sector_strength import sector_relative_strength
from scoring.sentiment import combined_sentiment_score
from scoring.technical import (
    breakout_score,
    macd_score,
    relative_strength_vs_spy,
    trend_score,
)
from services.qlib_integration import get_symbol_alpha_score
from screeners.base import BaseScreener, CandidateContext, WeightedSignal


class MediumScreener(BaseScreener):
    bucket = Bucket.medium

    def __init__(self, price_service: PriceService | None = None):
        self.ps = price_service or PriceService()

    def _spy(self):
        return self.ps.get_spy_history(period="1y")

    def hard_filter(self, ctx: CandidateContext, options: ScanOptions) -> bool:
        if not self.run_hard_filters_v3(ctx, options):
            return False
        price_min = options.min_price if options.min_price is not None else MEDIUM_PRICE_MIN
        price_max = options.max_price if options.max_price is not None else MEDIUM_PRICE_MAX
        min_vol = options.min_volume if options.min_volume is not None else MEDIUM_MIN_VOLUME

        if not (price_min <= ctx.price <= price_max):
            return False

        avg_vol = ctx.info.get("averageVolume") or avg_volume_from_history(ctx.history)
        if avg_vol < min_vol:
            return False

        dollar_vol = avg_dollar_volume_from_history(ctx.history)
        if dollar_vol < MEDIUM_MIN_DOLLAR_VOLUME_20D:
            return False

        mcap = ctx.info.get("marketCap") or 0
        if mcap and not (MEDIUM_MARKET_CAP_MIN <= mcap <= MEDIUM_MARKET_CAP_MAX):
            return False

        beta = ctx.info.get("beta")
        if beta is not None and not (0.5 <= beta <= 3.0):
            return False

        df = ctx.history
        if df is None or df.empty or len(df) < 55:
            return False

        trend_ok = trend_score(df) >= 55
        breakout_ok = breakout_score(df) >= 70
        if not (trend_ok or breakout_ok):
            return False

        if options.exclude_sectors:
            sector = (ctx.info.get("sector") or "").lower()
            if sector in [s.lower() for s in options.exclude_sectors]:
                return False

        return True

    def score(self, ctx: CandidateContext) -> tuple[float, list[WeightedSignal], RiskLevel, str, dict]:
        from config import OPENBB_ON_SCAN, SLEEVE_FACTORS_V3_ENABLED

        df = ctx.history
        spy = ctx.spy_history
        if spy is None or getattr(spy, "empty", True):
            spy = self._spy()
        sentiment_data = combined_sentiment_score(ctx.symbol, include_news=True)
        sector = ctx.info.get("sector")
        qlib_signal = 50.0
        qlib_source = "v3"
        ml_proxy = 50.0

        if SLEEVE_FACTORS_V3_ENABLED:
            from engines.factor.sleeve_signals import build_sleeve_signals

            signals = self.prepare_signals(ctx, build_sleeve_signals(ctx, "medium"))
        else:
            rs = relative_strength_vs_spy(df, spy, days=20)
            technical = (macd_score(df) + breakout_score(df) + trend_score(df)) / 3
            ml_proxy = ml_medium_horizon_score(df, spy)
            qlib_signal, qlib_source = get_symbol_alpha_score(Bucket.medium, ctx.symbol, ml_proxy)
            sector_strength = sector_relative_strength(df, sector, spy, self.ps.market, days=20)
            signals = [
                WeightedSignal("20d momentum vs SPY", rs, 0.22, "Relative strength vs benchmark"),
                WeightedSignal("Technical setup", technical, 0.23, "MACD, trend, breakout"),
                WeightedSignal("Sector RS vs SPY", sector_strength, 0.18, f"Stock vs {sector or 'sector'} ETF"),
                WeightedSignal("Qlib alpha (20d)", qlib_signal, 0.18, f"Model signal source: {qlib_source}"),
                WeightedSignal("Sentiment", sentiment_data["score"], 0.19, "Finnhub/StockTwits news"),
            ]
            from services.openbb_integration import append_governance_signal

            signals = append_governance_signal(signals, ctx.symbol, allow_fetch=OPENBB_ON_SCAN)
            signals = self.prepare_signals(ctx, signals)
        raw_score = self.composite_score(signals)
        score, regime_meta = self.apply_regime(ctx, raw_score)
        score = self.apply_score_cap(score, ctx)
        risk = RiskLevel.medium
        if score >= 75:
            risk = RiskLevel.low
        elif score < 50:
            risk = RiskLevel.high

        entry = ctx.price
        stop = round(entry * 0.93, 2)
        target = round(entry * 1.10, 2)
        summary = f"Swing candidate for 4-8 week hold. Entry ~${entry:.2f}, stop ~${stop}, target ~${target}."
        metrics = {
            "trend": "bullish" if trend_score(df) >= 60 else "neutral",
            "sector": sector,
            "sector_rs": round(sector_strength, 1),
            "beta": ctx.info.get("beta"),
            "news_red_flags": sentiment_data.get("red_flags", []),
            "entry": entry,
            "stop": stop,
            "target": target,
            "hold_horizon": "4-8 weeks",
            "ml_signal_proxy": round(ml_proxy, 1),
            "qlib_alpha_20d": round(qlib_signal, 1),
            "qlib_source": qlib_source,
            "regime": regime_meta,
            "raw_score": round(raw_score, 1),
        }
        return score, signals, risk, summary, metrics

    def enrich(self, symbol: str) -> CandidateContext | None:
        return build_candidate(
            symbol,
            history_period="1y",
            include_spy=True,
            spy_period="1y",
            price_service=self.ps,
        )
