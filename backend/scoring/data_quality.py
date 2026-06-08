"""Adjust scores based on cross-source data quality."""
from __future__ import annotations

from config import MIN_DATA_QUALITY_SCORE, MIN_HISTORY_BARS


def should_exclude_low_quality(
    quality_score: float | None,
    history_bars: int,
    *,
    min_quality: float | None = None,
    min_bars: int | None = None,
) -> tuple[bool, str]:
    """Hard exclude only when data is clearly unusable."""
    min_q = min_quality if min_quality is not None else MIN_DATA_QUALITY_SCORE
    min_h = min_bars if min_bars is not None else MIN_HISTORY_BARS

    if history_bars < min_h:
        return True, f"Insufficient history ({history_bars} < {min_h} bars)"

    if quality_score is not None and quality_score < min_q:
        return True, f"Data quality too low ({quality_score:.0f}% < {min_q:.0f}%)"

    return False, ""


def adjust_score_for_data_quality(score: float, quality_score: float | None) -> float:
    """Penalize composite score when reconciliation confidence is weak."""
    if quality_score is None:
        return score * 0.92  # unknown sources — slight penalty

    if quality_score >= 75:
        return score
    if quality_score >= 55:
        return score * 0.97
    if quality_score >= 40:
        return score * 0.90
    if quality_score >= 25:
        return score * 0.82
    return score * 0.70
