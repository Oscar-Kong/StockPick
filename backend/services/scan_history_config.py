"""Centralized strategy-aware history horizons by bucket and stage."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from config import (
    MIN_HISTORY_BARS,
    SCAN_COMPOUNDER_STAGE_A_PERIOD,
    SCAN_COMPOUNDER_STAGE_B_PERIOD,
    SCAN_PENNY_STAGE_A_PERIOD,
    SCAN_PENNY_STAGE_B_PERIOD,
)
from data.price_service import PERIOD_LIMIT, PERIOD_MIN_BARS
from models.schemas import Bucket

# Longest active penny indicator lookback (rel volume 21) + RSI warm-up (5)
# + return-shift (1) + safety buffer (5). No penny factor requires 252 bars.
PENNY_INDICATOR_HISTORY_FLOOR = 32

# Operational Stage B floor: matches historical quality_filters penny intent
# and clears default 6mo trim (160) while staying above indicator math.
PENNY_STAGE_B_MIN_BARS = 80
PENNY_STAGE_A_MIN_BARS = 21
COMPOUNDER_STAGE_A_MIN_BARS = 60

_DEFAULT_SESSION_LAG = 1


class ScanStage(str, Enum):
    STAGE_A = "stage_a"
    STAGE_B = "stage_b"
    ANALYZE = "analyze"


@dataclass(frozen=True)
class HistoryPolicy:
    requested_period: str
    returned_bar_limit: int
    minimum_required_bars: int
    preferred_bars: int
    allowed_session_lag: int

    def to_dict(self) -> dict:
        return asdict(self)


def _period_limit(period: str, default: int) -> int:
    return int(PERIOD_LIMIT.get(period, default))


def _period_min(period: str, default: int) -> int:
    return int(PERIOD_MIN_BARS.get(period, default))


def resolve_history_policy(bucket: Bucket, stage: ScanStage | str) -> HistoryPolicy:
    """Single source of truth for history length by sleeve and scan stage."""
    stage_key = ScanStage(stage) if not isinstance(stage, ScanStage) else stage

    if stage_key == ScanStage.ANALYZE:
        period = "1y"
        return HistoryPolicy(
            requested_period=period,
            returned_bar_limit=_period_limit(period, 280),
            minimum_required_bars=int(MIN_HISTORY_BARS),
            preferred_bars=_period_min(period, 200),
            allowed_session_lag=_DEFAULT_SESSION_LAG,
        )

    if bucket == Bucket.compounder:
        if stage_key == ScanStage.STAGE_A:
            period = SCAN_COMPOUNDER_STAGE_A_PERIOD
            return HistoryPolicy(
                requested_period=period,
                returned_bar_limit=_period_limit(period, 280),
                minimum_required_bars=COMPOUNDER_STAGE_A_MIN_BARS,
                preferred_bars=_period_min(period, 200),
                allowed_session_lag=_DEFAULT_SESSION_LAG,
            )
        period = SCAN_COMPOUNDER_STAGE_B_PERIOD
        return HistoryPolicy(
            requested_period=period,
            returned_bar_limit=_period_limit(period, 1400),
            minimum_required_bars=min(_period_min(period, 252), 252),
            preferred_bars=_period_min(period, 1000),
            allowed_session_lag=_DEFAULT_SESSION_LAG,
        )

    # Penny (and legacy medium → penny at API boundaries)
    if stage_key == ScanStage.STAGE_A:
        period = SCAN_PENNY_STAGE_A_PERIOD
        return HistoryPolicy(
            requested_period=period,
            returned_bar_limit=_period_limit(period, 160),
            minimum_required_bars=PENNY_STAGE_A_MIN_BARS,
            preferred_bars=_period_min(period, 100),
            allowed_session_lag=_DEFAULT_SESSION_LAG,
        )

    period = SCAN_PENNY_STAGE_B_PERIOD
    return HistoryPolicy(
        requested_period=period,
        returned_bar_limit=_period_limit(period, 160),
        minimum_required_bars=PENNY_STAGE_B_MIN_BARS,
        preferred_bars=_period_limit(period, 160),
        allowed_session_lag=_DEFAULT_SESSION_LAG,
    )


def stage_a_period(bucket: Bucket) -> str:
    return resolve_history_policy(bucket, ScanStage.STAGE_A).requested_period


def stage_b_period(bucket: Bucket) -> str:
    return resolve_history_policy(bucket, ScanStage.STAGE_B).requested_period


def stage_b_min_history_bars(bucket: Bucket, period: str | None = None) -> int:
    """Minimum OHLC bars required to accept preloaded bulk history for Stage B.

    ``period`` is retained for call-site compatibility; the resolved Stage B
    policy is authoritative (strategy-aware, not period-map alone).
    """
    _ = period  # callers may still pass period; policy owns the minimum
    return resolve_history_policy(bucket, ScanStage.STAGE_B).minimum_required_bars


def bulk_history_reusable(
    bucket: Bucket,
    *,
    bulk_bars: int,
    stage_a_period: str,
    stage_b_period: str,
) -> bool:
    """True when Stage A bulk OHLC satisfies Stage B policy without a reload.

    Gate and preload share ``minimum_required_bars``. When Stage B requests a
    longer horizon than Stage A (compounder 1y→5y), also require the Stage B
    period floor so short Stage A frames are not reused for deep scoring.
    """
    policy = resolve_history_policy(bucket, ScanStage.STAGE_B)
    if bulk_bars < policy.minimum_required_bars:
        return False
    if stage_a_period != stage_b_period:
        period_floor = _period_min(stage_b_period, policy.preferred_bars)
        return bulk_bars >= max(policy.minimum_required_bars, period_floor)
    return True


def compounder_stage_b_needs_fundamentals(bucket: Bucket) -> bool:
    return bucket == Bucket.compounder
