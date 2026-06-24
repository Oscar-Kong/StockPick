"""Base screener interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from models.schemas import Bucket, RiskLevel, ScanOptions, Signal, StockResult


def _opt_score(value) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


@dataclass
class WeightedSignal:
    name: str
    value: float
    weight: float
    description: str = ""

    @property
    def contribution(self) -> float:
        return self.value * self.weight


@dataclass
class CandidateContext:
    symbol: str
    price: float
    info: dict
    fundamentals: dict = field(default_factory=dict)
    history: object | None = None  # pandas DataFrame
    spy_history: object | None = None


class BaseScreener(ABC):
    bucket: Bucket

    @abstractmethod
    def hard_filter(self, ctx: CandidateContext, options: ScanOptions) -> bool:
        ...

    @abstractmethod
    def score(self, ctx: CandidateContext) -> tuple[float, list[WeightedSignal], RiskLevel, str, dict]:
        ...

    def to_result(
        self,
        ctx: CandidateContext,
        score: float,
        signals: list[WeightedSignal],
        risk: RiskLevel,
        summary: str,
        metrics: dict,
    ) -> StockResult:
        warnings = metrics.get("valuation_warnings") or []
        if isinstance(warnings, str):
            warnings = [warnings]
        days = metrics.get("days_until_earnings")
        return StockResult(
            symbol=ctx.symbol,
            price=ctx.price,
            score=round(score, 1),
            alpha_score=_opt_score(metrics.get("alpha_score")),
            confidence_score=_opt_score(metrics.get("confidence_score")),
            tradability_score=_opt_score(metrics.get("tradability_score")),
            ranking_score=_opt_score(metrics.get("ranking_score") or score),
            signals=[
                Signal(
                    name=s.name,
                    value=round(s.value, 1),
                    weight=s.weight,
                    contribution=round(s.contribution, 1),
                    description=s.description,
                )
                for s in signals
            ],
            risk_level=risk,
            summary=summary,
            bucket=self.bucket,
            metrics=metrics,
            valuation_warnings=list(warnings),
            earnings_date=metrics.get("earnings_date"),
            days_until_earnings=int(days) if days is not None else None,
            earnings_soon=bool(metrics.get("earnings_soon")),
        )

    def run_hard_filters_v3(self, ctx: CandidateContext, options: ScanOptions) -> bool:
        from engines.filters.hard_filters import (
            apply_hard_filters_to_context,
            evaluate_hard_filters,
        )

        sleeve = self.bucket.value if hasattr(self.bucket, "value") else str(self.bucket)
        result = evaluate_hard_filters(sleeve, ctx, options)
        apply_hard_filters_to_context(ctx, result)
        return result.passed

    def apply_score_cap(self, score: float, ctx: CandidateContext) -> float:
        cap = ctx.info.get("_hard_filter_score_cap")
        if cap is not None:
            return min(score, float(cap))
        return score

    def prepare_signals(self, ctx: CandidateContext, signals: list[WeightedSignal]) -> list[WeightedSignal]:
        """Apply dynamic weights when DYNAMIC_WEIGHTS_ENABLED."""
        from config import DYNAMIC_WEIGHTS_ENABLED

        if not DYNAMIC_WEIGHTS_ENABLED:
            return signals
        try:
            from engines.weighting.weight_store import WeightStore

            sleeve = self.bucket.value if hasattr(self.bucket, "value") else str(self.bucket)
            return WeightStore.apply_to_signals(signals, sleeve)
        except Exception:
            return signals

    @staticmethod
    def composite_score(signals: list[WeightedSignal]) -> float:
        total_weight = sum(s.weight for s in signals)
        if total_weight <= 0:
            return 0.0
        return sum(s.contribution for s in signals) / total_weight

    def apply_regime(self, ctx: CandidateContext, raw_score: float) -> tuple[float, dict]:
        from scoring.regime import apply_regime_to_score

        bucket = self.bucket.value if hasattr(self.bucket, "value") else str(self.bucket)
        return apply_regime_to_score(
            raw_score,
            bucket,
            sector=ctx.info.get("sector"),
            stock_df=ctx.history,
            spy_df=ctx.spy_history,
        )
