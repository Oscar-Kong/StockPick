"""Unified Stage B eligibility gate — single seam for data-quality and filter policy."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from data.quality_filters import QualityFilterResult, apply_quality_filters
from models.schemas import Bucket, ScanOptions
from scoring.data_quality import should_exclude_low_quality
from screeners.base import BaseScreener, CandidateContext
from services.scan_skip_reasons import (
    INVALID_PRICE,
    STRICT_FILTER_REJECTION,
    map_quality_exclusion_reason,
)


@dataclass(frozen=True)
class CandidateGateResult:
    passed: bool
    skip_reason: str | None = None
    skip_detail: str | None = None
    quality_filter: dict[str, Any] | None = None


def evaluate_stage_b_gate(
    *,
    ctx: CandidateContext,
    symbol: str,
    bucket: Bucket,
    screener: BaseScreener,
    options: ScanOptions,
    quality_score: float | None,
    hist_len: int,
) -> CandidateGateResult:
    """Apply price, DQ exclusion, hard_filter, and quality_filters in one place."""
    price = ctx.price
    if price is None or not math.isfinite(float(price)) or float(price) <= 0:
        return CandidateGateResult(
            passed=False,
            skip_reason=INVALID_PRICE,
            skip_detail=str(price),
        )

    exclude, exclude_reason = should_exclude_low_quality(quality_score, hist_len)
    if exclude:
        return CandidateGateResult(
            passed=False,
            skip_reason=map_quality_exclusion_reason(exclude_reason, hist_len),
            skip_detail=exclude_reason,
        )

    if not screener.hard_filter(ctx, options):
        return CandidateGateResult(
            passed=False,
            skip_reason=STRICT_FILTER_REJECTION,
            skip_detail="hard_filter",
        )

    qf: QualityFilterResult = apply_quality_filters(
        symbol,
        bucket,
        ctx.price,
        ctx.history,
        ctx.info,
    )
    if not qf.passed:
        return CandidateGateResult(
            passed=False,
            skip_reason=STRICT_FILTER_REJECTION,
            skip_detail="; ".join(qf.reasons) if qf.reasons else "quality_filter",
        )

    return CandidateGateResult(passed=True, quality_filter=qf.to_dict())
