"""Regression tests for scan pipeline correctness fixes."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.candidate_builder import build_candidate
from data.candidate_gate import CandidateGateResult
from data.quality_filters import QualityFilterResult
from models.schemas import Bucket, ScanStatus
from screeners.base import CandidateContext
from services.scan_manager import ScanManager
from services.stage_a_ranking import StageACandidate, StageARankingResult


def _make_history(symbol: str, *, base: float = 10.0, bars: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=bars, freq="B")
    closes = [base + i * 0.05 for i in range(bars)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.2 for c in closes],
            "low": [c - 0.2 for c in closes],
            "close": closes,
            "volume": [1_500_000] * bars,
        }
    )


def _make_ctx(symbol: str) -> CandidateContext:
    history = _make_history(symbol)
    return CandidateContext(
        symbol=symbol.upper(),
        price=float(history["close"].iloc[-1]),
        info={"sector": "Technology", "marketCap": 5_000_000_000},
        fundamentals={},
        history=history,
    )


def test_build_candidate_fills_market_info_from_history_when_provider_sparse():
    """When reconcile=False and provider info lacks price/mcap, use PriceService.quote_from_history."""
    hist = _make_history("SPARSE")
    ps = MagicMock()
    ps.get_history.return_value = hist
    ps.get_info.return_value = {}
    ps.quote_from_history.return_value = {
        "symbol": "SPARSE",
        "currentPrice": 12.5,
        "averageVolume": 1_500_000.0,
    }
    ps.get_spy_history.return_value = None

    ctx = build_candidate("SPARSE", reconcile=False, price_service=ps)

    assert ctx is not None
    assert ctx.info.get("currentPrice") == 12.5
    assert ctx.price == float(hist["close"].iloc[-1])
    ps.quote_from_history.assert_called_once_with("SPARSE", hist)


def test_build_candidate_uses_preloaded_history_without_refetch():
    """Stage B bulk-history fallback must not re-download OHLC."""
    hist = _make_history("BULK")
    ps = MagicMock()
    ps.get_info.return_value = {"currentPrice": 11.0, "marketCap": 1_000_000_000}
    ps.get_spy_history.return_value = None

    ctx = build_candidate("BULK", reconcile=False, price_service=ps, history=hist)

    assert ctx is not None
    assert len(ctx.history) == 60
    ps.get_history.assert_not_called()


def test_partial_data_fallback_candidates_returned_when_strict_filters_reject_all():
    """Regression: partial-data fallback must survive quality_score being defined before use."""
    manager = ScanManager()
    job = manager.create_job(Bucket.penny)
    symbol = "FALLBACK"
    bulk_hist = {symbol: _make_history(symbol)}
    ctx = _make_ctx(symbol)
    mock_screener = MagicMock()
    mock_screener.hard_filter.return_value = False
    mock_screener.to_result.side_effect = (
        lambda ctx, score, signals, risk, summary, metrics, **kwargs: MagicMock(
            symbol=ctx.symbol,
            score=score,
            metrics=metrics,
            risk_level=risk,
            summary=summary,
            signals=signals,
        )
    )
    saved: dict = {}

    with (
        patch("services.scan_pipeline.get_universe", return_value=[symbol]),
        patch("services.scan_pipeline.UNIVERSE_SCAN_BATCH_SIZE", 0),
        patch(
            "services.scan_pipeline.rank_stage_a_candidates",
            return_value=StageARankingResult(
                ranked=[
                    StageACandidate(
                        symbol=symbol.upper(),
                        pre_score=90.0,
                        features={"mock": 90.0},
                        rank=1,
                    )
                ],
                excluded=[],
            ),
        ),
        patch(
            "services.scan_pipeline.evaluate_stage_b_gate",
            return_value=CandidateGateResult(passed=False, quality_filter={}, skip_reason="hard_filter"),
        ),
        patch(
            "services.scan_pipeline.enrich_scan_display",
            side_effect=lambda info, fund, hist, metrics, legacy_summary="": (legacy_summary, metrics),
        ),
        patch("services.scan_pipeline._resolve_stage_b_context", return_value=ctx),
        patch("services.scan_pipeline.StrategyRegistry") as reg_cls,
        patch("services.scan_pipeline.HistoricalStore"),
        patch("services.scan_pipeline.cache_module.save_scan_snapshot"),
        patch(
            "services.scan_pipeline.cache_module.save_scan_results",
            side_effect=lambda bucket, results, completed_at, ttl, **kw: saved.update(
                {"results": results, "metadata": kw.get("metadata")}
            ),
        ),
        patch("services.scan_pipeline.cache_module.clear_scan_attempt_failure"),
        patch.object(manager, "_get_screener", return_value=mock_screener),
        patch("services.scan_pipeline.PriceService") as ps_cls,
    ):
        ps_cls.return_value.download_batch.return_value = bulk_hist
        reg_cls.return_value.get_active.return_value = MagicMock(version_id="test-v1")
        options = MagicMock(max_results=25, mode="deep")
        options.model_dump.return_value = {"max_results": 25, "mode": "deep"}
        manager.run_scan(job.job_id, options)

    finished = manager.get_job(job.job_id)
    assert finished.status == ScanStatus.completed
    assert len(finished.results) == 1
    assert finished.results[0].metrics.get("provider_limited_partial_data") is True
    assert "partial-data fallback" in (finished.message or "").lower()


def test_scan_records_skip_reason_when_history_missing():
    manager = ScanManager()
    job = manager.create_job(Bucket.penny)
    symbol = "MISSING"
    saved: dict = {}

    with (
        patch("services.scan_pipeline.get_universe", return_value=[symbol]),
        patch("services.scan_pipeline.UNIVERSE_SCAN_BATCH_SIZE", 0),
        patch(
            "services.scan_pipeline.rank_stage_a_candidates",
            return_value=StageARankingResult(
                ranked=[
                    StageACandidate(
                        symbol=symbol.upper(),
                        pre_score=90.0,
                        features={"mock": 90.0},
                        rank=1,
                    )
                ],
                excluded=[],
            ),
        ),
        patch("services.scan_pipeline.build_candidate", return_value=None),
        patch("services.scan_pipeline.StrategyRegistry") as reg_cls,
        patch("services.scan_pipeline.HistoricalStore"),
        patch("services.scan_pipeline.cache_module.save_scan_snapshot"),
        patch(
            "services.scan_pipeline.cache_module.save_scan_results",
            side_effect=lambda bucket, results, completed_at, ttl, **kw: saved.update(
                {"metadata": kw.get("metadata")}
            ),
        ),
        patch("services.scan_pipeline.cache_module.clear_scan_attempt_failure"),
        patch.object(manager, "_get_screener", return_value=MagicMock()),
        patch("services.scan_pipeline.PriceService") as ps_cls,
    ):
        ps_cls.return_value.download_batch.return_value = {}
        reg_cls.return_value.get_active.return_value = MagicMock(version_id="test-v1")
        options = MagicMock(max_results=25, mode="deep")
        options.model_dump.return_value = {"max_results": 25, "mode": "deep"}
        manager.run_scan(job.job_id, options)

    skipped = saved["metadata"]["skipped_candidates"]
    assert len(skipped) == 1
    assert skipped[0]["symbol"] == symbol
    assert skipped[0]["reason"] == "missing_history"


def test_scan_records_strict_filter_rejection_reason():
    manager = ScanManager()
    job = manager.create_job(Bucket.penny)
    symbol = "REJECT"
    ctx = _make_ctx(symbol)
    mock_screener = MagicMock()
    mock_screener.hard_filter.return_value = False
    saved: dict = {}

    with (
        patch("services.scan_pipeline.get_universe", return_value=[symbol]),
        patch("services.scan_pipeline.UNIVERSE_SCAN_BATCH_SIZE", 0),
        patch(
            "services.scan_pipeline.rank_stage_a_candidates",
            return_value=StageARankingResult(
                ranked=[
                    StageACandidate(
                        symbol=symbol.upper(),
                        pre_score=90.0,
                        features={"mock": 90.0},
                        rank=1,
                    )
                ],
                excluded=[],
            ),
        ),
        patch("services.scan_pipeline.build_candidate", return_value=ctx),
        patch("services.scan_pipeline.StrategyRegistry") as reg_cls,
        patch("services.scan_pipeline.HistoricalStore"),
        patch("services.scan_pipeline.cache_module.save_scan_snapshot"),
        patch(
            "services.scan_pipeline.cache_module.save_scan_results",
            side_effect=lambda bucket, results, completed_at, ttl, **kw: saved.update(
                {"metadata": kw.get("metadata")}
            ),
        ),
        patch("services.scan_pipeline.cache_module.clear_scan_attempt_failure"),
        patch("services.scan_scoring_config.resolve_scan_scoring_mode", return_value="legacy"),
        patch("services.scan_pipeline.resolve_scan_scoring_mode", return_value="legacy"),
        patch("data.candidate_gate.should_exclude_low_quality", return_value=(False, "")),
        patch.object(manager, "_get_screener", return_value=mock_screener),
        patch("services.scan_pipeline.PriceService") as ps_cls,
        patch(
            "services.scan_pipeline.enrich_scan_display",
            side_effect=lambda info, fund, hist, metrics, legacy_summary="": (legacy_summary, metrics),
        ),
    ):
        ps_cls.return_value.download_batch.return_value = {symbol: ctx.history}
        reg_cls.return_value.get_active.return_value = MagicMock(version_id="test-v1")
        options = MagicMock(max_results=25, mode="deep")
        options.model_dump.return_value = {"max_results": 25, "mode": "deep"}
        manager.run_scan(job.job_id, options)

    reasons = [row["reason"] for row in saved["metadata"]["skipped_candidates"]]
    assert "strict_filter_rejection" in reasons
