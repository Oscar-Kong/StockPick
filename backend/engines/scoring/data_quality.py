"""Data quality gates — unified entry for v2 scoring (wraps scoring.data_quality)."""
from __future__ import annotations

from scoring.data_quality import (  # noqa: F401
    adjust_score_for_data_quality,
    should_exclude_low_quality,
)


def dq_multiplier(quality_score: float | None) -> float:
    """Multiplier applied to post-regime score (matches adjust_score_for_data_quality ratios)."""
    if quality_score is None:
        return 0.92
    if quality_score >= 75:
        return 1.0
    if quality_score >= 55:
        return 0.97
    if quality_score >= 40:
        return 0.90
    if quality_score >= 25:
        return 0.82
    return 0.70
