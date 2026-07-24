"""Strategy-aware HistoryPolicy resolver."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas import Bucket
from services.scan_history_config import (
    PENNY_INDICATOR_HISTORY_FLOOR,
    HistoryPolicy,
    ScanStage,
    resolve_history_policy,
    stage_b_min_history_bars,
)


def test_penny_indicator_floor_documented():
    assert PENNY_INDICATOR_HISTORY_FLOOR == 32


def test_penny_stage_a_policy():
    policy = resolve_history_policy(Bucket.penny, ScanStage.STAGE_A)
    assert isinstance(policy, HistoryPolicy)
    assert policy.requested_period == "6mo"
    assert policy.returned_bar_limit == 160
    assert policy.minimum_required_bars == 21
    assert policy.preferred_bars == 100
    assert policy.allowed_session_lag == 1


def test_penny_stage_b_policy_aligned_with_quality_intent():
    policy = resolve_history_policy(Bucket.penny, ScanStage.STAGE_B)
    assert policy.requested_period == "6mo"
    assert policy.returned_bar_limit == 160
    assert policy.minimum_required_bars == 80
    assert policy.preferred_bars == 160
    assert policy.allowed_session_lag == 1
    assert policy.minimum_required_bars >= PENNY_INDICATOR_HISTORY_FLOOR
    assert policy.minimum_required_bars <= policy.returned_bar_limit


def test_compounder_stage_policies():
    stage_a = resolve_history_policy(Bucket.compounder, ScanStage.STAGE_A)
    assert stage_a.requested_period == "1y"
    assert stage_a.returned_bar_limit == 280
    assert stage_a.minimum_required_bars == 60
    assert stage_a.preferred_bars == 200

    stage_b = resolve_history_policy(Bucket.compounder, ScanStage.STAGE_B)
    assert stage_b.requested_period == "5y"
    assert stage_b.returned_bar_limit == 1400
    assert stage_b.minimum_required_bars == 252
    assert stage_b.preferred_bars == 1000


def test_analyze_default_keeps_global_252():
    policy = resolve_history_policy(Bucket.penny, ScanStage.ANALYZE)
    assert policy.requested_period == "1y"
    assert policy.minimum_required_bars == 252
    assert policy.returned_bar_limit == 280


def test_stage_b_min_history_bars_delegates_to_policy():
    assert stage_b_min_history_bars(Bucket.penny, "6mo") == 80
    assert stage_b_min_history_bars(Bucket.compounder, "5y") == 252


def test_six_month_frame_satisfies_penny_stage_b_gate_floor():
    """Regression: trimmed 6mo frames (~160) must clear penny Stage B min."""
    policy = resolve_history_policy(Bucket.penny, ScanStage.STAGE_B)
    assert 160 >= policy.minimum_required_bars
    assert 160 < 252  # still below the old global constant


def test_compounder_does_not_reuse_stage_a_one_year_for_stage_b():
    from services.scan_history_config import bulk_history_reusable

    # Stage A 1y trim (~280) clears the 252 gate floor but must not skip 5y reload.
    assert (
        bulk_history_reusable(
            Bucket.compounder,
            bulk_bars=280,
            stage_a_period="1y",
            stage_b_period="5y",
        )
        is False
    )
    assert (
        bulk_history_reusable(
            Bucket.penny,
            bulk_bars=160,
            stage_a_period="6mo",
            stage_b_period="6mo",
        )
        is True
    )
