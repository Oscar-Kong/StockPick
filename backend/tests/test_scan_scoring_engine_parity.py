"""Tests for ScanManager Stage B ScoringEngine routing."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stub ta.* before engines/scoring import chain (optional dep in some envs).
if "ta" not in sys.modules:
    _ta = MagicMock()
    sys.modules["ta"] = _ta
    sys.modules["ta.momentum"] = _ta.momentum
    sys.modules["ta.trend"] = _ta.trend
    sys.modules["ta.volatility"] = _ta.volatility

from models.schemas import Bucket, RiskLevel
from screeners.base import CandidateContext, WeightedSignal
from services.scan_parity import aggregate_scan_parity_summary
from services.scan_scoring import log_score_parity, score_stage_b_candidate


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


def _mock_scoring_result(*, final: float = 68.0, sleeve: str = "medium") -> SimpleNamespace:
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
        sleeve=sleeve,
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


def _stock_result_fields(outcome) -> dict:
    """Fields mirrored by scan_manager → screener.to_result → StockResult."""
    return {
        "score": outcome.score,
        "signals": outcome.signals,
        "risk": outcome.risk,
        "summary": outcome.summary,
        "metrics": outcome.metrics,
    }


def _enrich_side_effect(sym, info, fund, m, bucket, **kw):
    return {**m, "enriched": True}


def test_legacy_path_preserves_result_shape():
    with (
        patch("services.scan_scoring.USE_SCORING_ENGINE_IN_SCAN", False),
        patch("services.scan_scoring.enrich_metrics", side_effect=_enrich_side_effect),
        patch("services.scan_scoring._apply_openbb_adjustment", side_effect=lambda score, metrics: score),
    ):
        for bucket in (Bucket.penny, Bucket.medium, Bucket.compounder):
            ctx = _mock_ctx(f"LEG{bucket.value[:3].upper()}")
            screener = _mock_screener(bucket)
            outcome = score_stage_b_candidate(
                ctx=ctx,
                screener=screener,
                bucket=bucket,
                symbol=ctx.symbol,
                quality_score=80.0,
                strategy_version="test-v1",
                quality_filter={"passed": True},
            )
            fields = _stock_result_fields(outcome)
            assert 0 <= fields["score"] <= 100
            assert fields["signals"]
            assert fields["risk"] in (RiskLevel.low, RiskLevel.medium, RiskLevel.high)
            assert isinstance(fields["summary"], str)
            assert fields["metrics"]["strategy_version"] == "test-v1"
            assert fields["metrics"]["quality_filter"]["passed"] is True
            assert "parity_delta" not in fields["metrics"]
            assert outcome.scoring_engine_used is False
            assert outcome.parity_record is None
            screener.score.assert_called_once()


def test_engine_path_bounded_score_and_shape():
    with (
        patch("services.scan_scoring.USE_SCORING_ENGINE_IN_SCAN", True),
        patch("services.scan_scoring.PERSIST_SCORE_ATTRIBUTION", False),
        patch("services.scan_scoring.enrich_metrics", side_effect=_enrich_side_effect),
        patch("services.scan_scoring._apply_openbb_adjustment", side_effect=lambda score, metrics: score),
        patch("services.scan_scoring.ScoringEngine.score") as mock_engine_score,
    ):
        for bucket in (Bucket.penny, Bucket.medium, Bucket.compounder):
            ctx = _mock_ctx(f"ENG{bucket.value[:3].upper()}")
            screener = _mock_screener(bucket)
            mock_engine_score.return_value = _mock_scoring_result(final=71.3, sleeve=bucket.value)
            outcome = score_stage_b_candidate(
                ctx=ctx,
                screener=screener,
                bucket=bucket,
                symbol=ctx.symbol,
                quality_score=80.0,
                strategy_version="test-v2",
                quality_filter={"passed": True},
            )
            assert 0 <= outcome.score <= 100
            assert outcome.scoring_engine_used is True
            assert outcome.metrics["scoring_engine"] is True
            assert outcome.metrics["strategy_version"] == "test-v2"
            assert _stock_result_fields(outcome)["signals"]
            assert outcome.parity_record is not None
            assert outcome.parity_record.sleeve == bucket.value
            assert outcome.metrics["parity"]["symbol"] == ctx.symbol
            mock_engine_score.assert_called()


def test_parity_delta_recorded_and_logged():
    with (
        patch("services.scan_scoring.USE_SCORING_ENGINE_IN_SCAN", True),
        patch("services.scan_scoring.PERSIST_SCORE_ATTRIBUTION", False),
        patch("services.scan_scoring.enrich_metrics", side_effect=_enrich_side_effect),
        patch("services.scan_scoring._apply_openbb_adjustment", side_effect=lambda score, metrics: score),
        patch("services.scan_scoring.ScoringEngine.score") as mock_engine_score,
        patch.object(logging.getLogger("services.scan_parity"), "info") as log_info,
    ):
        mock_engine_score.return_value = _mock_scoring_result(final=60.0)

        ctx = _mock_ctx("PARITY")
        screener = _mock_screener(Bucket.medium)
        outcome = score_stage_b_candidate(
            ctx=ctx,
            screener=screener,
            bucket=Bucket.medium,
            symbol=ctx.symbol,
            quality_score=80.0,
            strategy_version="test-v2",
            quality_filter={"passed": True},
        )

        assert outcome.parity_delta is not None
        assert outcome.metrics["parity_delta"] == outcome.parity_delta
        assert outcome.metrics["legacy_score"] == outcome.legacy_score
        assert outcome.parity_delta == abs(outcome.legacy_score - outcome.score)
        assert outcome.parity_record.top_factor_contributions
        assert any("Scan score parity" in str(c.args[0]) for c in log_info.call_args_list)

    record = log_score_parity(
        symbol="PARITY",
        sleeve="medium",
        legacy_score=72.5,
        engine_score=60.0,
        factors=_mock_scoring_result().factors,
    )
    assert record.parity_delta == 12.5


def test_engine_path_per_bucket_parity_summary():
    """Penny, medium, compounder each produce aggregatable parity records."""
    records = []
    engine_scores = {
        Bucket.penny: 55.0,
        Bucket.medium: 60.0,
        Bucket.compounder: 78.0,
    }
    with (
        patch("services.scan_scoring.USE_SCORING_ENGINE_IN_SCAN", True),
        patch("services.scan_scoring.PERSIST_SCORE_ATTRIBUTION", False),
        patch("services.scan_scoring.enrich_metrics", side_effect=_enrich_side_effect),
        patch("services.scan_scoring._apply_openbb_adjustment", side_effect=lambda score, metrics: score),
        patch("services.scan_scoring.ScoringEngine.score") as mock_engine_score,
    ):
        for bucket in (Bucket.penny, Bucket.medium, Bucket.compounder):
            ctx = _mock_ctx(f"SUM{bucket.value[:3].upper()}")
            screener = _mock_screener(bucket)
            final = engine_scores[bucket]
            mock_engine_score.return_value = _mock_scoring_result(final=final, sleeve=bucket.value)
            outcome = score_stage_b_candidate(
                ctx=ctx,
                screener=screener,
                bucket=bucket,
                symbol=ctx.symbol,
                quality_score=80.0,
                strategy_version="test-v2",
                quality_filter={"passed": True},
            )
            assert outcome.parity_record is not None
            records.append(outcome.parity_record)

    summary = aggregate_scan_parity_summary(records)
    assert summary is not None
    assert summary.symbol_count == 3
    assert summary.max_delta >= 0
    assert summary.average_delta >= 0


if __name__ == "__main__":
    test_legacy_path_preserves_result_shape()
    test_engine_path_bounded_score_and_shape()
    test_parity_delta_recorded_and_logged()
    test_engine_path_per_bucket_parity_summary()
    print("scan scoring engine parity tests passed")
