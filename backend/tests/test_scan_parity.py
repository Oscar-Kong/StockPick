"""Tests for scan parity aggregation and per-bucket Stage B records."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas import Bucket
from services.scan_parity import (
    PARITY_DELTA_ALERT_THRESHOLD,
    StageBParityRecord,
    aggregate_scan_parity_summary,
    build_stage_b_parity_record,
    top_factor_contributions,
)


def _factors(*contributions: float) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            factor_id=f"f{i}",
            display_name=f"Factor {i}",
            contribution=c,
            norm_score=50.0 + c,
            weight=0.2,
        )
        for i, c in enumerate(contributions)
    ]


def test_top_factor_contributions_sorted_by_abs():
    ranked = top_factor_contributions(_factors(5.0, -12.0, 3.0), limit=2)
    assert len(ranked) == 2
    assert ranked[0]["factor_id"] == "f1"
    assert ranked[0]["contribution"] == -12.0


def test_build_stage_b_parity_record_per_bucket():
    for bucket in (Bucket.penny, Bucket.compounder):
        record = build_stage_b_parity_record(
            symbol=f"TST{bucket.value[:2].upper()}",
            sleeve=bucket.value,
            legacy_score=72.0,
            engine_score=58.0,
            factors=_factors(10.0, 8.0),
        )
        assert record.sleeve == bucket.value
        assert record.parity_delta == 14.0
        assert record.scoring_engine_used is True
        assert record.legacy_recommendation_bucket == "buy"
        assert record.engine_recommendation_bucket == "watch"
        assert record.recommendation_bucket_differs is True
        assert record.top_factor_contributions


def test_aggregate_scan_parity_summary_metrics():
    records = [
        StageBParityRecord(
            symbol="A",
            sleeve="penny",
            legacy_score=81.0,
            engine_score=70.0,
            parity_delta=11.0,
            scoring_engine_used=True,
            legacy_recommendation_bucket="strong_buy",
            engine_recommendation_bucket="buy",
            recommendation_bucket_differs=True,
        ),
        StageBParityRecord(
            symbol="B",
            sleeve="penny",
            legacy_score=60.0,
            engine_score=60.0,
            parity_delta=0.0,
            scoring_engine_used=True,
            legacy_recommendation_bucket="watch",
            engine_recommendation_bucket="watch",
            recommendation_bucket_differs=False,
        ),
        StageBParityRecord(
            symbol="C",
            sleeve="penny",
            legacy_score=55.0,
            engine_score=40.0,
            parity_delta=15.0,
            scoring_engine_used=True,
            legacy_recommendation_bucket="watch",
            engine_recommendation_bucket="hold",
            recommendation_bucket_differs=True,
        ),
    ]
    summary = aggregate_scan_parity_summary(records)
    assert summary is not None
    assert summary.symbol_count == 3
    assert summary.average_delta == round((11.0 + 0.0 + 15.0) / 3, 2)
    assert summary.max_delta == 15.0
    assert summary.symbols_delta_gt_10 == 2
    assert summary.recommendation_bucket_diffs == 2
    assert summary.scoring_engine_used is True
    assert len(summary.to_dict()["records"]) == 3


def test_aggregate_empty_returns_none():
    assert aggregate_scan_parity_summary([]) is None


def test_parity_delta_threshold_constant():
    assert PARITY_DELTA_ALERT_THRESHOLD == 10.0
