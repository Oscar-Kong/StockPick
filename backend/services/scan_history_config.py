"""Centralized scan history horizons by bucket and stage."""
from __future__ import annotations

from config import (
    SCAN_COMPOUNDER_STAGE_A_PERIOD,
    SCAN_COMPOUNDER_STAGE_B_PERIOD,
    SCAN_PENNY_STAGE_A_PERIOD,
    SCAN_PENNY_STAGE_B_PERIOD,
)
from data.price_service import PERIOD_MIN_BARS
from models.schemas import Bucket


def stage_a_period(bucket: Bucket) -> str:
    if bucket == Bucket.compounder:
        return SCAN_COMPOUNDER_STAGE_A_PERIOD
    return SCAN_PENNY_STAGE_A_PERIOD


def stage_b_period(bucket: Bucket) -> str:
    if bucket == Bucket.compounder:
        return SCAN_COMPOUNDER_STAGE_B_PERIOD
    return SCAN_PENNY_STAGE_B_PERIOD


def stage_b_min_history_bars(bucket: Bucket, period: str) -> int:
    """Minimum OHLC bars required to accept preloaded bulk history for Stage B."""
    if bucket == Bucket.compounder:
        # Compounder hard filter needs ~1y; full smooth-growth prefers 5y when available.
        return min(PERIOD_MIN_BARS.get(period, 252), 252)
    return PERIOD_MIN_BARS.get(period, 21)


def bulk_history_reusable(
    bucket: Bucket,
    *,
    bulk_bars: int,
    stage_a_period: str,
    stage_b_period: str,
) -> bool:
    """True when Stage A bulk OHLC satisfies Stage B horizon without a reload."""
    if bulk_bars < stage_b_min_history_bars(bucket, stage_b_period):
        return False
    required = PERIOD_MIN_BARS.get(stage_b_period, stage_b_min_history_bars(bucket, stage_b_period))
    return bulk_bars >= required


def compounder_stage_b_needs_fundamentals(bucket: Bucket) -> bool:
    return bucket == Bucket.compounder
