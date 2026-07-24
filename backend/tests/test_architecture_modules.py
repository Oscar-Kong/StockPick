"""Tests for centralized architecture modules."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.candidate_gate import CandidateGateResult, evaluate_stage_b_gate
from data.pit_history import truncate_history
from engines.factor.composite import composite_score
from screeners.base import WeightedSignal
from services.scan_fallback_score import compute_partial_data_fallback_score
from services.scan_pipeline import _apply_canonical_scores
from services.scan_decomposition import DecomposedScanScore
from models.schemas import Bucket, StockResult


def test_truncate_history_no_lookahead():
    hist = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=5, freq="B"), "close": [1, 2, 3, 4, 5]}
    )
    hist["date"] = hist["date"].dt.date
    trimmed = truncate_history(hist, date(2024, 1, 3))
    assert len(trimmed) == 3
    assert trimmed["date"].max() <= date(2024, 1, 3)


def test_composite_score_unified():
    signals = [
        WeightedSignal(name="a", value=80, weight=1.0),
        WeightedSignal(name="b", value=60, weight=1.0),
    ]
    assert composite_score(signals) == pytest.approx(70.0)


def test_fallback_score_from_history():
    hist = pd.DataFrame(
        {
            "close": [10.0] * 20 + [12.0],
            "volume": [1000.0] * 21,
        }
    )
    score = compute_partial_data_fallback_score(hist)
    assert score is not None
    assert 0 <= score <= 100


def test_candidate_gate_rejects_low_quality():
    ctx = MagicMock()
    ctx.price = 5.0
    ctx.history = pd.DataFrame({"close": [1.0] * 5, "volume": [1_000_000] * 5})
    ctx.info = {}
    screener = MagicMock()
    screener.hard_filter.return_value = True
    options = MagicMock()
    result = evaluate_stage_b_gate(
        ctx=ctx,
        symbol="TEST",
        bucket=Bucket.penny,
        screener=screener,
        options=options,
        quality_score=10.0,
        hist_len=5,
    )
    assert isinstance(result, CandidateGateResult)
    assert result.passed is False
    assert result.history_gate_exclusion is True


def test_apply_canonical_scores_sets_metrics():
    result = StockResult(symbol="AAPL", price=10.0, score=50.0, bucket=Bucket.penny, summary="x")
    decomposed = DecomposedScanScore(
        alpha_score=70.0,
        confidence_score=65.0,
        tradability_score=60.0,
        ranking_score=68.0,
    )
    _apply_canonical_scores(result, decomposed, stage_b_score=72.0)
    assert result.ranking_score == 68.0
    assert result.score == 68.0
    assert result.metrics["stage_b_score"] == 72.0
    assert result.metrics["ranking_score"] == 68.0
