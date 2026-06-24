"""Compounder screener — long-term quality growers."""
from __future__ import annotations

from config import COMPOUNDER_MARKET_CAP_MIN
from data.candidate_builder import build_candidate
from data.fred_client import FredClient
from data.price_service import PriceService
from models.schemas import Bucket, RiskLevel, ScanOptions
from scoring.fundamental import (
    moat_proxy_score,
    quality_filter_passes,
    revenue_eps_consistency_score,
    roic_margin_stability_score,
)
from scoring.technical import smooth_growth_score_with_horizon
from services.qlib_integration import get_symbol_alpha_score
from screeners.base import BaseScreener, CandidateContext, WeightedSignal


class CompounderScreener(BaseScreener):
    bucket = Bucket.compounder

    def __init__(
        self,
        price_service: PriceService | None = None,
        fred_client: FredClient | None = None,
    ):
        self.ps = price_service or PriceService()
        self.fred = fred_client or FredClient()
        self._macro_score: float | None = None

    def _macro(self) -> float:
        if self._macro_score is None:
            self._macro_score = self.fred.macro_regime_score()
        return self._macro_score

    def hard_filter(self, ctx: CandidateContext, options: ScanOptions) -> bool:
        if not self.run_hard_filters_v3(ctx, options):
            return False
        if not quality_filter_passes(ctx.info, ctx.fundamentals, COMPOUNDER_MARKET_CAP_MIN):
            return False
        if options.exclude_sectors:
            sector = (ctx.info.get("sector") or ctx.fundamentals.get("sector") or "").lower()
            if sector in [s.lower() for s in options.exclude_sectors]:
                return False
        df = ctx.history
        if df is None or df.empty or len(df) < 252:
            return False
        return True

    def score(self, ctx: CandidateContext) -> tuple[float, list[WeightedSignal], RiskLevel, str, dict]:
        from config import OPENBB_ON_SCAN, SLEEVE_FACTORS_V3_ENABLED

        df = ctx.history
        qlib_alpha = 50.0
        missing_all: list[str] = []
        smooth_meta = {}
        if SLEEVE_FACTORS_V3_ENABLED:
            from engines.factor.sleeve_signals import build_sleeve_signals

            signals = self.prepare_signals(ctx, build_sleeve_signals(ctx, "compounder"))
            qlib_source = "v3"
        else:
            rev_eps = revenue_eps_consistency_score(ctx.info, ctx.fundamentals)
            roic = roic_margin_stability_score(ctx.info, ctx.fundamentals)
            smooth = (
                smooth_growth_score_with_horizon(df, years=5)
                if df is not None and not df.empty
                else smooth_growth_score_with_horizon(df, years=5)
            )
            moat = moat_proxy_score(ctx.info, ctx.fundamentals)
            macro = self._macro()
            missing_all = sorted(
                set(rev_eps.missing_fields + roic.missing_fields + moat.missing_fields)
            )
            smooth_meta = {
                "smooth_growth_label": smooth.label,
                "smooth_growth_bars_used": smooth.bars_used,
                "smooth_growth_years_effective": smooth.years_effective,
                "smooth_growth_years_requested": smooth.years_requested,
            }
            qlib_fallback = (float(rev_eps) + float(roic) + smooth.score) / 3
            qlib_alpha, qlib_source = get_symbol_alpha_score(Bucket.compounder, ctx.symbol, qlib_fallback)
            signals = [
                WeightedSignal(
                    "Revenue/EPS consistency",
                    float(rev_eps),
                    0.28,
                    "Steady earnings and revenue growth",
                ),
                WeightedSignal(
                    "ROIC & margins",
                    float(roic),
                    0.24,
                    "Profitability and balance sheet quality",
                ),
                WeightedSignal(
                    smooth.label,
                    smooth.score,
                    0.20,
                    f"Low-volatility upward trend ({smooth.bars_used} bars)",
                ),
                WeightedSignal("Moat proxies", float(moat), 0.13, "Margins, FCF, sector quality"),
                WeightedSignal("Macro regime", macro, 0.10, "Economic backdrop for long holds"),
                WeightedSignal("Qlib alpha", qlib_alpha, 0.05, f"Model signal source: {qlib_source}"),
            ]
            from services.openbb_integration import append_governance_signal

            signals = append_governance_signal(signals, ctx.symbol, allow_fetch=OPENBB_ON_SCAN)
            signals = self.prepare_signals(ctx, signals)
        raw_score = self.composite_score(signals)
        score, regime_meta = self.apply_regime(ctx, raw_score)
        confidence_penalty = float(ctx.info.get("_fundamental_confidence_penalty") or 0.0)
        if confidence_penalty > 0:
            score = max(0.0, score - confidence_penalty * 0.25)
        score = self.apply_score_cap(score, ctx)
        risk = RiskLevel.low if score >= 70 else RiskLevel.medium

        rev = ctx.info.get("revenueGrowth") or ctx.fundamentals.get("revenue_growth")
        name = ctx.info.get("shortName") or ctx.fundamentals.get("name") or ctx.symbol
        summary = f"{name}: quality compounder candidate with score {score:.0f}/100"
        if missing_all:
            summary += f" (confidence reduced — missing {len(missing_all)} fundamental fields)"

        metrics = {
            "sector": ctx.info.get("sector") or ctx.fundamentals.get("sector"),
            "market_cap": ctx.info.get("marketCap") or ctx.fundamentals.get("market_cap"),
            "revenue_growth": rev,
            "hold_horizon": "3-10+ years",
            "style": "Costco-like steady grower",
            "qlib_alpha": round(qlib_alpha, 1),
            "qlib_source": qlib_source,
            "regime": regime_meta,
            "raw_score": round(raw_score, 1),
            "missing_fundamental_fields": missing_all or ctx.info.get("_missing_fundamental_fields", []),
            "fundamental_confidence_penalty": confidence_penalty,
            "scan_diagnostics": ctx.info.get("_scan_diagnostics"),
            **smooth_meta,
        }
        return score, signals, risk, summary, metrics

    def enrich(self, symbol: str) -> CandidateContext | None:
        return build_candidate(
            symbol,
            history_period="5y",
            reconcile=True,
            fundamentals_policy="cache_first",
            price_service=self.ps,
        )
