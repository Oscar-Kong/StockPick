"""Tests for scan scoring modes — legacy, engine, parity_sample."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas import Bucket, RiskLevel
from screeners.base import CandidateContext, WeightedSignal
from services.scan_scoring import prepare_candidate_features, score_stage_b_candidate
from services.scan_scoring_config import parity_sample_included, resolve_scan_scoring_mode


def _mock_ctx(symbol: str = "TEST") -> CandidateContext:
    dates = pd.date_range("2025-01-01", periods=60, freq="B")
    closes = [10.0 + i * 0.05 for i in range(60)]
    history = pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.2 for c in closes],
            "low": [c - 0.2 for c in closes],
            "close": closes,
            "volume": [1_000_000] * 60,
        }
    )
    return CandidateContext(
        symbol=symbol,
        price=closes[-1],
        info={"sector": "Technology", "marketCap": 5_000_000_000, "_reconcile_quality": 80.0},
        fundamentals={},
        history=history,
    )


def _mock_screener(bucket: Bucket) -> MagicMock:
    screener = MagicMock()
    screener.bucket = bucket
    signals = [WeightedSignal("Test signal", 70.0, 1.0, "mock")]
    screener.score.return_value = (
        72.5,
        signals,
        RiskLevel.medium,
        "Legacy summary",
        {"hold_horizon": "test", "raw_score": 72.5},
    )
    return screener


def _mock_scoring_result(*, final: float = 68.0) -> SimpleNamespace:
    signals = [WeightedSignal("Engine signal", 68.0, 1.0, "engine")]
    factors = [
        SimpleNamespace(
            factor_id="test_factor",
            display_name="Engine signal",
            norm_score=68.0,
            weight=1.0,
            contribution=68.0,
            description="engine",
        )
    ]
    return SimpleNamespace(
        sleeve="penny",
        signals=signals,
        factors=factors,
        raw_score=68.0,
        score_after_regime=68.0,
        regime_mult=1.0,
        sector_tilt=0.0,
        dq_multiplier=1.0,
        score_after_dq=68.0,
        openbb_delta=0.0,
        score_after_openbb=68.0,
        final_score=final,
        risk_level=RiskLevel.medium,
        summary="Engine summary",
        metrics={"regime": {}},
    )


def _enrich_side_effect(sym, info, fund, m, bucket, **kw):
    return {**m, "enriched": True}


@pytest.fixture
def scoring_patches():
    with (
        patch("services.scan_scoring.enrich_metrics", side_effect=_enrich_side_effect) as enrich,
        patch("services.scan_scoring._apply_openbb_adjustment", side_effect=lambda score, metrics: score),
        patch("services.scan_scoring.PERSIST_SCORE_ATTRIBUTION", False),
        patch("services.scan_scoring.ScoringEngine.score") as engine_score,
    ):
        engine_score.return_value = _mock_scoring_result(final=71.0)
        yield enrich, engine_score


def test_legacy_mode_never_calls_scoring_engine(scoring_patches):
    enrich, engine_score = scoring_patches
    ctx = _mock_ctx("LEG")
    screener = _mock_screener(Bucket.penny)
    outcome = score_stage_b_candidate(
        ctx=ctx,
        screener=screener,
        bucket=Bucket.penny,
        symbol=ctx.symbol,
        quality_score=80.0,
        strategy_version="test-v1",
        quality_filter={"passed": True},
        scan_id="scan-legacy",
        scoring_mode="legacy",
    )
    screener.score.assert_called_once()
    engine_score.assert_not_called()
    assert outcome.scoring_engine_used is False
    assert outcome.score == pytest.approx(72.5)
    assert outcome.legacy_invoked is True
    assert outcome.engine_invoked is False
    enrich.assert_called_once()


def test_engine_mode_never_calls_legacy_scorer(scoring_patches):
    enrich, engine_score = scoring_patches
    ctx = _mock_ctx("ENG")
    screener = _mock_screener(Bucket.penny)
    outcome = score_stage_b_candidate(
        ctx=ctx,
        screener=screener,
        bucket=Bucket.penny,
        symbol=ctx.symbol,
        quality_score=80.0,
        strategy_version="test-v2",
        quality_filter={"passed": True},
        scan_id="scan-engine",
        scoring_mode="engine",
    )
    screener.score.assert_not_called()
    engine_score.assert_called_once()
    assert outcome.scoring_engine_used is True
    assert outcome.score == pytest.approx(71.0)
    assert outcome.legacy_invoked is False
    assert outcome.engine_invoked is True
    assert outcome.parity_record is None
    enrich.assert_called_once()


def test_parity_mode_calls_both_only_for_sampled_candidates(scoring_patches):
    _, engine_score = scoring_patches
    scan_id = "scan-parity-fixed"
    sampled_symbol = "AAA"
    while not parity_sample_included(scan_id, sampled_symbol, sample_rate=0.10):
        sampled_symbol = sampled_symbol + "X"

    unsampled = "ZZZNOTSAMPLED"
    attempts = 0
    while parity_sample_included(scan_id, unsampled, sample_rate=0.10) and attempts < 50:
        unsampled = unsampled + "Q"
        attempts += 1
    assert not parity_sample_included(scan_id, unsampled, sample_rate=0.10)

    screener_sampled = _mock_screener(Bucket.penny)
    outcome_sampled = score_stage_b_candidate(
        ctx=_mock_ctx(sampled_symbol),
        screener=screener_sampled,
        bucket=Bucket.penny,
        symbol=sampled_symbol,
        quality_score=80.0,
        strategy_version="test-v2",
        quality_filter={"passed": True},
        scan_id=scan_id,
        scoring_mode="parity_sample",
    )
    screener_sampled.score.assert_called_once()
    assert outcome_sampled.engine_invoked is True
    assert outcome_sampled.parity_record is not None
    assert outcome_sampled.score == pytest.approx(71.0)

    screener_unsampled = _mock_screener(Bucket.penny)
    outcome_unsampled = score_stage_b_candidate(
        ctx=_mock_ctx(unsampled),
        screener=screener_unsampled,
        bucket=Bucket.penny,
        symbol=unsampled,
        quality_score=80.0,
        strategy_version="test-v2",
        quality_filter={"passed": True},
        scan_id=scan_id,
        scoring_mode="parity_sample",
    )
    screener_unsampled.score.assert_not_called()
    assert outcome_unsampled.engine_invoked is True
    assert outcome_unsampled.parity_record is None
    assert outcome_unsampled.score == pytest.approx(71.0)
    assert engine_score.call_count == 2


def test_parity_sampling_is_deterministic():
    scan_id = "job-123"
    symbol = "AAPL"
    first = parity_sample_included(scan_id, symbol, sample_rate=0.25)
    second = parity_sample_included(scan_id, symbol, sample_rate=0.25)
    assert first == second


def test_production_ranking_uses_primary_scorer(scoring_patches):
    _, engine_score = scoring_patches
    engine_score.return_value = _mock_scoring_result(final=88.0)
    ctx = _mock_ctx("PROD")
    screener = _mock_screener(Bucket.compounder)
    screener.score.return_value = (
        55.0,
        [WeightedSignal("Legacy", 55.0, 1.0, "")],
        RiskLevel.medium,
        "Legacy",
        {},
    )
    with patch(
        "services.scan_scoring.legacy_parity_comparison_enabled",
        return_value=True,
    ):
        outcome = score_stage_b_candidate(
            ctx=ctx,
            screener=screener,
            bucket=Bucket.compounder,
            symbol=ctx.symbol,
            quality_score=80.0,
            strategy_version="test-v2",
            quality_filter={"passed": True},
            scan_id="scan-prod",
            scoring_mode="parity_sample",
        )
    assert outcome.score == pytest.approx(88.0)
    assert outcome.scoring_engine_used is True


def test_enrichment_not_duplicated_per_candidate(scoring_patches):
    enrich, _ = scoring_patches
    ctx = _mock_ctx("ENR")
    screener = _mock_screener(Bucket.penny)
    score_stage_b_candidate(
        ctx=ctx,
        screener=screener,
        bucket=Bucket.penny,
        symbol=ctx.symbol,
        quality_score=80.0,
        strategy_version="test-v2",
        quality_filter={"passed": True},
        scan_id="scan-enrich",
        scoring_mode="engine",
    )
    assert enrich.call_count == 1

    enrich.reset_mock()
    with patch(
        "services.scan_scoring.legacy_parity_comparison_enabled",
        return_value=True,
    ):
        score_stage_b_candidate(
            ctx=ctx,
            screener=screener,
            bucket=Bucket.penny,
            symbol=ctx.symbol,
            quality_score=80.0,
            strategy_version="test-v2",
            quality_filter={"passed": True},
            scan_id="scan-enrich-parity",
            scoring_mode="parity_sample",
        )
    assert enrich.call_count == 1


def test_resolve_mode_fallback_from_legacy_flag():
    with patch("services.scan_scoring_config.SCAN_SCORING_MODE", ""):
        with patch("services.scan_scoring_config.USE_SCORING_ENGINE_IN_SCAN", False):
            # Canonical default is engine when mode is unset.
            assert resolve_scan_scoring_mode() == "engine"
        with patch("services.scan_scoring_config.USE_SCORING_ENGINE_IN_SCAN", True):
            assert resolve_scan_scoring_mode() == "engine"


def test_resolve_mode_explicit_legacy_still_works():
    with patch("services.scan_scoring_config.SCAN_SCORING_MODE", "legacy"):
        with patch("services.scan_scoring_config.USE_SCORING_ENGINE_IN_SCAN", False):
            assert resolve_scan_scoring_mode() == "legacy"


def test_prepare_candidate_features_returns_shared_bundle():
    with patch("services.scan_scoring.enrich_metrics", side_effect=_enrich_side_effect):
        ctx = _mock_ctx("FEAT")
        bundle = prepare_candidate_features(
            ctx=ctx,
            bucket=Bucket.penny,
            symbol=ctx.symbol,
            quality_score=80.0,
        )
        assert bundle.enriched_metrics.get("enriched") is True
        assert bundle.base_display_metrics.get("sector") == "Technology"
