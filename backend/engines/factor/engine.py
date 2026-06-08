"""FactorEngine — registry-backed factor computation."""
from __future__ import annotations

from dataclasses import dataclass

from engines.factor.catalog import signal_name_to_factor_id
from engines.factor.sleeve_signals import build_sleeve_signals
from screeners.base import CandidateContext, WeightedSignal


@dataclass
class FactorValue:
    factor_id: str
    display_name: str
    norm_score: float
    weight: float
    contribution: float
    description: str = ""


class FactorEngine:
    """Compute normalized factor values for a candidate context."""

    @staticmethod
    def build_signals(ctx: CandidateContext, sleeve: str) -> list[WeightedSignal]:
        from config import DYNAMIC_WEIGHTS_ENABLED

        signals = build_sleeve_signals(ctx, sleeve)
        if DYNAMIC_WEIGHTS_ENABLED:
            from engines.weighting.weight_store import WeightStore

            signals = WeightStore.apply_to_signals(signals, sleeve)
        return signals

    @classmethod
    def compute(cls, ctx: CandidateContext, sleeve: str) -> list[FactorValue]:
        signals = cls.build_signals(ctx, sleeve)
        return cls.from_signals(signals, sleeve)

    @staticmethod
    def from_signals(signals: list[WeightedSignal], sleeve: str) -> list[FactorValue]:
        out: list[FactorValue] = []
        for sig in signals:
            fid = signal_name_to_factor_id(sleeve, sig.name)
            out.append(
                FactorValue(
                    factor_id=fid,
                    display_name=sig.name,
                    norm_score=round(sig.value, 2),
                    weight=sig.weight,
                    contribution=round(sig.contribution, 2),
                    description=sig.description,
                )
            )
        return out

    @staticmethod
    def composite_score(signals: list[WeightedSignal]) -> float:
        total_weight = sum(s.weight for s in signals)
        if total_weight <= 0:
            return 0.0
        return sum(s.contribution for s in signals) / total_weight
