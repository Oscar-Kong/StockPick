"""Governance / SEC risk scoring via OpenBB (when enabled)."""
from __future__ import annotations


def adjust_score_for_governance(score: float, governance_score: float | None) -> float:
    """Lower governance_score (0–100) applies a small penalty to the composite."""
    if governance_score is None:
        return score
    if governance_score >= 75:
        return score
    if governance_score >= 60:
        return score * 0.98
    if governance_score >= 45:
        return score * 0.94
    if governance_score >= 30:
        return score * 0.88
    return score * 0.82
