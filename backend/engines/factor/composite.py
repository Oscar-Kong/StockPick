"""Canonical weighted-signal composite — single implementation for FactorEngine and screeners."""
from __future__ import annotations

from screeners.base import WeightedSignal


def composite_score(signals: list[WeightedSignal]) -> float:
    total_weight = sum(s.weight for s in signals)
    if total_weight <= 0:
        return 0.0
    return sum(s.contribution for s in signals) / total_weight
