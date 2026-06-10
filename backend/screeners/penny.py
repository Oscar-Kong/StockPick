"""Penny stock screener — short-term momentum plays."""
from __future__ import annotations

from config import (
    PENNY_MARKET_CAP_MAX,
    PENNY_MARKET_CAP_MIN,
    PENNY_MIN_DATA_QUALITY_SCORE,
    PENNY_MIN_DOLLAR_VOLUME_20D,
    PENNY_MIN_SPREAD_SCORE,
    PENNY_MIN_VOLUME,
    PENNY_PRICE_MAX,
    PENNY_PRICE_MIN,
)
from data.candidate_builder import build_candidate
from data.price_service import (
    PriceService,
    avg_dollar_volume_from_history,
    avg_volume_from_history,
)
from data.reconciler import DataReconciler
from models.schemas import Bucket, RiskLevel, ScanOptions
from scoring.sentiment import combined_sentiment_score
from scoring.technical import (
    momentum_score,
    rsi_score,
    spread_proxy_score,
    volatility_fit_score,
    volume_spike_score,
)
from screeners.base import BaseScreener, CandidateContext, WeightedSignal
from screeners.penny_setup import classify_penny_setup


class PennyScreener(BaseScreener):
    bucket = Bucket.penny

    def __init__(self, price_service: PriceService | None = None):
        self.ps = price_service or PriceService()

    def hard_filter(self, ctx: CandidateContext, options: ScanOptions) -> bool:
        if not self.run_hard_filters_v3(ctx, options):
            return False
        price_min = options.min_price if options.min_price is not None else PENNY_PRICE_MIN
        price_max = options.max_price if options.max_price is not None else PENNY_PRICE_MAX
        min_vol = options.min_volume if options.min_volume is not None else PENNY_MIN_VOLUME

        if not (price_min <= ctx.price <= price_max):
            return False

        avg_vol = ctx.info.get("averageVolume") or avg_volume_from_history(ctx.history)
        if avg_vol < min_vol:
            return False

        dollar_vol = avg_dollar_volume_from_history(ctx.history)
        if dollar_vol < PENNY_MIN_DOLLAR_VOLUME_20D:
            return False

        mcap = ctx.info.get("marketCap") or 0
        if mcap and not (PENNY_MARKET_CAP_MIN <= mcap <= PENNY_MARKET_CAP_MAX):
            return False

        df = ctx.history
        if df is None or df.empty or len(df) < 21:
            return False

        spread_score = spread_proxy_score(df)
        if spread_score < PENNY_MIN_SPREAD_SCORE:
            return False

        try:
            rec = DataReconciler().reconcile(ctx.symbol)
            if rec.quality_score < PENNY_MIN_DATA_QUALITY_SCORE:
                return False
        except Exception:
            pass

        exchange = (ctx.info.get("exchange") or ctx.info.get("fullExchangeName") or "").upper()
        if "OTC" in exchange or "PINK" in exchange:
            return False

        if options.exclude_sectors:
            sector = (ctx.info.get("sector") or "").lower()
            if sector in [s.lower() for s in options.exclude_sectors]:
                return False

        return True

    def score(self, ctx: CandidateContext) -> tuple[float, list[WeightedSignal], RiskLevel, str, dict]:
        from config import SLEEVE_FACTORS_V3_ENABLED

        df = ctx.history
        warnings: list[str] = []
        dq_score: float | None = None
        try:
            rec = DataReconciler().reconcile(ctx.symbol)
            dq_score = rec.quality_score
            for flag in rec.flags or []:
                if "split" in flag.lower() or "dilut" in flag.lower():
                    warnings.append(flag)
        except Exception:
            pass

        if SLEEVE_FACTORS_V3_ENABLED:
            from engines.factor.sleeve_signals import build_sleeve_signals

            signals = self.prepare_signals(ctx, build_sleeve_signals(ctx, "penny"))
            sentiment_data = combined_sentiment_score(ctx.symbol, include_news=True)
        else:
            sentiment_data = combined_sentiment_score(ctx.symbol, include_news=True)
            spread_val = spread_proxy_score(df)
            signals = [
                WeightedSignal("Volume spike", volume_spike_score(df), 0.28, "Today vs 20-day average volume"),
                WeightedSignal("5-day momentum", momentum_score(df, 5), 0.24, "Recent price momentum"),
                WeightedSignal("Social buzz", sentiment_data["score"], 0.18, "StockTwits + news sentiment"),
                WeightedSignal("Volatility fit", volatility_fit_score(df), 0.12, "ATR-based tradeability"),
                WeightedSignal("RSI fit", rsi_score(df), 0.10, "Not overbought"),
                WeightedSignal("Liquidity/spread", spread_val, 0.08, "Bid-ask proxy from OHLC"),
            ]
            signals = self.prepare_signals(ctx, signals)
        raw_score = self.composite_score(signals)
        score, regime_meta = self.apply_regime(ctx, raw_score)
        score = self.apply_score_cap(score, ctx)
        risk = RiskLevel.high

        vol_ratio = volume_spike_score(df) / 100
        setup_type, setup_notes = classify_penny_setup(
            ctx,
            signals,
            score=score,
            data_quality_score=dq_score,
            warnings=warnings,
        )
        summary = (
            f"Penny {setup_type.replace('_', ' ')}; hold 3-10 days. "
            f"Volume ~{vol_ratio:.1f}x baseline."
        )
        metrics = {
            "momentum_5d": momentum_score(df, 5),
            "volume_ratio": round(vol_ratio, 2),
            "sentiment": round(sentiment_data.get("stocktwits", sentiment_data["score"]), 1),
            "hold_horizon": "3-10 days",
            "sector": ctx.info.get("sector"),
            "regime": regime_meta,
            "raw_score": round(raw_score, 1),
            "setup_type": setup_type,
            "setup_notes": setup_notes,
            "data_quality_score": dq_score,
            "spread_score": round(spread_proxy_score(df), 1),
            "dilution_warnings": warnings,
        }
        return score, signals, risk, summary, metrics

    def enrich(self, symbol: str) -> CandidateContext | None:
        return build_candidate(
            symbol,
            history_period="6mo",
            reconcile=True,
            price_service=self.ps,
        )
