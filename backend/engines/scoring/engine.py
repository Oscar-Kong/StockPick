"""ScoringEngine — explicit score pipeline with attribution fields."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engines.factor.engine import FactorEngine, FactorValue
from engines.scoring.data_quality import dq_multiplier
from models.schemas import RiskLevel
from scoring.regime import apply_regime_to_score
from screeners.base import CandidateContext, WeightedSignal
@dataclass
class ScoringResult:
    sleeve: str
    signals: list[WeightedSignal]
    factors: list[FactorValue]
    raw_score: float
    score_after_regime: float
    regime_mult: float
    sector_tilt: float
    regime_meta: dict[str, Any] = field(default_factory=dict)
    dq_multiplier: float = 1.0
    score_after_dq: float = 0.0
    openbb_delta: float = 0.0
    score_after_openbb: float = 0.0
    final_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.medium
    summary: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


class ScoringEngine:
    @classmethod
    def score(
        cls,
        ctx: CandidateContext,
        sleeve: str,
        *,
        quality_score: float | None = None,
        apply_openbb: bool = True,
        metrics: dict[str, Any] | None = None,
    ) -> ScoringResult:
        signals = FactorEngine.build_signals(ctx, sleeve)
        factors = FactorEngine.from_signals(signals, sleeve)
        raw = round(FactorEngine.composite_score(signals), 2)

        score_regime, regime_meta = apply_regime_to_score(
            raw,
            sleeve,
            sector=ctx.info.get("sector"),
            stock_df=ctx.history,
            spy_df=ctx.spy_history,
        )
        regime_mult = float(regime_meta.get("final_multiplier") or 1.0)
        sector_meta = regime_meta.get("sector_regime") or {}
        sector_tilt = float(sector_meta.get("tilt") or 0.0)

        mult = dq_multiplier(quality_score)
        after_dq = round(max(0.0, min(100.0, score_regime * mult)), 2)

        m = dict(metrics or {})
        m.setdefault("regime", regime_meta)
        m.setdefault("raw_score", raw)

        after_openbb = after_dq
        openbb_delta = 0.0
        if apply_openbb:
            try:
                from services.openbb_integration import apply_openbb_score_adjustment

                adjusted = apply_openbb_score_adjustment(after_dq, m)
                openbb_delta = round(adjusted - after_dq, 2)
                after_openbb = round(adjusted, 2)
            except Exception:
                after_openbb = after_dq

        final = round(max(0.0, min(100.0, after_openbb)), 2)
        cap = ctx.info.get("_hard_filter_score_cap")
        if cap is not None:
            final = min(final, float(cap))
        risk = cls._infer_risk(sleeve, final)
        summary = cls._build_summary(ctx, sleeve, final, m)

        return ScoringResult(
            sleeve=sleeve,
            signals=signals,
            factors=factors,
            raw_score=raw,
            score_after_regime=score_regime,
            regime_mult=regime_mult,
            sector_tilt=sector_tilt,
            regime_meta=regime_meta,
            dq_multiplier=mult,
            score_after_dq=after_dq,
            openbb_delta=openbb_delta,
            score_after_openbb=after_openbb,
            final_score=final,
            risk_level=risk,
            summary=summary,
            metrics=m,
        )

    @staticmethod
    def _infer_risk(sleeve: str, score: float) -> RiskLevel:
        if sleeve == "penny":
            return RiskLevel.high
        if sleeve == "compounder":
            return RiskLevel.low if score >= 70 else RiskLevel.medium
        if score >= 75:
            return RiskLevel.low
        if score < 50:
            return RiskLevel.high
        return RiskLevel.medium

    @staticmethod
    def _build_summary(ctx: CandidateContext, sleeve: str, score: float, metrics: dict[str, Any]) -> str:
        if sleeve == "penny":
            vol_ratio = (metrics.get("volume_ratio") or 1.0)
            return (
                f"Short-term penny momentum play; suggested hold 3-10 days. "
                f"Volume activity ~{vol_ratio:.1f}x baseline. Score {score:.0f}/100."
            )
        if sleeve == "compounder":
            name = ctx.info.get("shortName") or ctx.fundamentals.get("name") or ctx.symbol
            return f"{name}: quality compounder candidate with score {score:.0f}/100"
        entry = ctx.price
        stop = round(entry * 0.93, 2)
        target = round(entry * 1.10, 2)
        return (
            f"Swing candidate for 4-8 week hold. Entry ~${entry:.2f}, stop ~${stop}, "
            f"target ~${target}. Score {score:.0f}/100."
        )
