"""Penny stock screener — short-term momentum plays."""
from __future__ import annotations

from config import (
    PENNY_MARKET_CAP_MAX,
    PENNY_MARKET_CAP_MIN,
    PENNY_MAX_SPREAD_PCT,
    PENNY_MIN_DATA_QUALITY_SCORE,
    PENNY_MIN_DOLLAR_VOLUME_20D,
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
from scoring.penny_liquidity import (
    compute_penny_liquidity_metrics,
    detect_penny_risk_warnings,
    spread_estimate_pct,
)
from scoring.sentiment import combined_sentiment_score
from scoring.technical import (
    momentum_score,
    spread_proxy_score,
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

        spread_pct = spread_estimate_pct(df)
        if spread_pct is not None and spread_pct > PENNY_MAX_SPREAD_PCT:
            return False

        try:
            dq = ctx.info.get("_reconcile_quality")
            if dq is not None and dq < PENNY_MIN_DATA_QUALITY_SCORE:
                return False
            if dq is None:
                from services.scan_context import is_bulk_scan

                if not is_bulk_scan():
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
        df = ctx.history
        reconcile_flags: list[str] = []
        warnings: list[str] = []
        dq_score: float | None = ctx.info.get("_reconcile_quality")
        if dq_score is None:
            from services.scan_context import is_bulk_scan

            if not is_bulk_scan():
                try:
                    rec = DataReconciler().reconcile(ctx.symbol)
                    dq_score = rec.quality_score
                    reconcile_flags = list(rec.flags or [])
                    for flag in reconcile_flags:
                        if "split" in flag.lower() or "dilut" in flag.lower():
                            warnings.append(flag)
                except Exception:
                    pass

        liquidity = compute_penny_liquidity_metrics(df)
        mom_5d = momentum_score(df, 5)
        risk_warnings = detect_penny_risk_warnings(
            liquidity,
            df,
            momentum_5d_score=mom_5d,
            min_dollar_volume_warn=PENNY_MIN_DOLLAR_VOLUME_20D,
            data_quality_score=dq_score,
            reconcile_flags=reconcile_flags,
        )
        seen: set[str] = set(warnings)
        for w in liquidity.warnings + risk_warnings:
            if w not in seen:
                seen.add(w)
                warnings.append(w)

        # Canonical Stage B legs/weights live in engines.factor.sleeve_signals
        # (shared with ScoringEngine). Liquidity/spread stays in metrics + setup,
        # not as a separate composite leg — matches FACTOR_CATALOG / engine path.
        from engines.factor.sleeve_signals import build_sleeve_signals

        signals = self.prepare_signals(ctx, build_sleeve_signals(ctx, "penny"))
        sentiment_data = combined_sentiment_score(ctx.symbol, include_news=True)
        raw_score = self.composite_score(signals)
        score, regime_meta = self.apply_regime(ctx, raw_score)
        score = self.apply_score_cap(score, ctx)
        risk = RiskLevel.high

        setup_type, setup_notes = classify_penny_setup(
            ctx,
            signals,
            score=score,
            data_quality_score=dq_score,
            warnings=warnings,
        )

        ratio = liquidity.relative_volume_ratio
        vol_score = liquidity.relative_volume_score
        if ratio is not None:
            summary = (
                f"Penny {setup_type.replace('_', ' ')}; hold 3-10 days. "
                f"Relative volume {ratio:.1f}x (signal {vol_score:.0f}/100)."
            )
        else:
            summary = (
                f"Penny {setup_type.replace('_', ' ')}; hold 3-10 days. "
                f"Volume signal {vol_score:.0f}/100 (baseline unavailable)."
            )

        metrics = {
            "momentum_5d": mom_5d,
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
        metrics.update(liquidity.to_metrics_dict())
        return score, signals, risk, summary, metrics

    def enrich(self, symbol: str) -> CandidateContext | None:
        return build_candidate(
            symbol,
            history_period="6mo",
            reconcile=True,
            price_service=self.ps,
        )
