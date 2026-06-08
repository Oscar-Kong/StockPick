"""Append OpenAlpha-inspired signals when OPENALPHA_FACTORS_ENABLED."""
from __future__ import annotations

from config import OPENALPHA_FACTORS_ENABLED
from engines.factor.expr import formulas_for_sleeve, evaluate_formula
from screeners.base import CandidateContext, WeightedSignal


def append_openalpha_signals(
    sleeve: str,
    ctx: CandidateContext,
    signals: list[WeightedSignal],
) -> list[WeightedSignal]:
    if not OPENALPHA_FACTORS_ENABLED:
        return signals
    df = ctx.history
    spy = ctx.spy_history
    if df is None or getattr(df, "empty", True):
        return signals
    extra: list[WeightedSignal] = []
    for formula in formulas_for_sleeve(sleeve):
        if not formula.enabled_live:
            continue
        score = evaluate_formula(formula, df, spy)
        if score is None:
            continue
        extra.append(
            WeightedSignal(
                formula.display_name,
                score,
                formula.weight,
                f"OpenAlpha {formula.openalpha_ref}: {formula.expression}",
            )
        )
    if not extra:
        return signals
    oa_weight = sum(s.weight for s in extra)
    scale = max(0.01, 1.0 - oa_weight)
    base_sum = sum(s.weight for s in signals) or 1.0
    scaled = [
        WeightedSignal(s.name, s.value, round(s.weight / base_sum * scale, 4), s.description)
        for s in signals
    ]
    return scaled + extra
