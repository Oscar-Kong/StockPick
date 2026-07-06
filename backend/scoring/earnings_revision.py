"""Earnings revision proxy score (non-sleeve-specific)."""
from __future__ import annotations

from scoring.metrics import safe_float


def earnings_revision_proxy(info: dict, fundamentals: dict) -> float:
    eps_g = safe_float(info.get("earningsGrowth"), default=0.0)
    rev_g = safe_float(info.get("revenueGrowth"), default=0.0)
    eps_est = safe_float(fundamentals.get("eps_estimate") or fundamentals.get("eps_growth_estimate"))
    score = 50.0
    if eps_g > 0.15:
        score += 25
    elif eps_g > 0.05:
        score += 12
    elif eps_g < -0.05:
        score -= 20
    if rev_g > 0.10:
        score += 10
    elif rev_g < 0:
        score -= 10
    if eps_est > eps_g and eps_est > 0:
        score += 8
    return max(0.0, min(100.0, score))
