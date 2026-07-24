"""Unified Stage B eligibility gate — single seam for data-quality and filter policy."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from data.quality_filters import QualityFilterResult, apply_quality_filters
from models.schemas import Bucket, ScanOptions
from scoring.data_quality import should_exclude_low_quality
from screeners.base import BaseScreener, CandidateContext
from services.scan_history_config import HistoryPolicy, ScanStage, resolve_history_policy
from services.scan_skip_reasons import (
    INSUFFICIENT_HISTORY,
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
    history_gate_exclusion: bool = False
    history_policy_min_bars: int | None = None


def evaluate_stage_b_gate(
    *,
    ctx: CandidateContext,
    symbol: str,
    bucket: Bucket,
    screener: BaseScreener,
    options: ScanOptions,
    quality_score: float | None,
    hist_len: int,
    history_policy: HistoryPolicy | None = None,
    min_bars: int | None = None,
) -> CandidateGateResult:
    """Apply price, DQ exclusion, hard_filter, and quality_filters in one place."""
    policy = history_policy or resolve_history_policy(bucket, ScanStage.STAGE_B)
    required_bars = min_bars if min_bars is not None else policy.minimum_required_bars

    price = ctx.price
    if price is None or not math.isfinite(float(price)) or float(price) <= 0:
        return CandidateGateResult(
            passed=False,
            skip_reason=INVALID_PRICE,
            skip_detail=str(price),
            history_policy_min_bars=required_bars,
        )

    exclude, exclude_reason = should_exclude_low_quality(
        quality_score,
        hist_len,
        min_bars=required_bars,
    )
    if exclude:
        skip_reason = map_quality_exclusion_reason(exclude_reason, hist_len)
        return CandidateGateResult(
            passed=False,
            skip_reason=skip_reason,
            skip_detail=exclude_reason,
            history_gate_exclusion=skip_reason == INSUFFICIENT_HISTORY
            or "insufficient history" in (exclude_reason or "").lower(),
            history_policy_min_bars=required_bars,
        )

    if not screener.hard_filter(ctx, options):
        return CandidateGateResult(
            passed=False,
            skip_reason=STRICT_FILTER_REJECTION,
            skip_detail="hard_filter",
            history_policy_min_bars=required_bars,
        )

    qf: QualityFilterResult = apply_quality_filters(
        symbol,
        bucket,
        ctx.price,
        ctx.history,
        ctx.info,
        min_bars=required_bars,
    )
    if not qf.passed:
        detail = "; ".join(qf.reasons) if qf.reasons else "quality_filter"
        history_excl = any("insufficient history" in r.lower() for r in qf.reasons)
        return CandidateGateResult(
            passed=False,
            skip_reason=STRICT_FILTER_REJECTION if not history_excl else INSUFFICIENT_HISTORY,
            skip_detail=detail,
            history_gate_exclusion=history_excl,
            history_policy_min_bars=required_bars,
        )

    return CandidateGateResult(
        passed=True,
        quality_filter=qf.to_dict(),
        history_policy_min_bars=required_bars,
    )
