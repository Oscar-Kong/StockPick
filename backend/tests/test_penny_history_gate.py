"""Regression: penny Stage B history gate must not use global MIN_HISTORY_BARS=252."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.candidate_gate import evaluate_stage_b_gate
from models.schemas import Bucket, RiskLevel, ScanOptions, ScanStatus, StockResult
from scoring.data_quality import should_exclude_low_quality
from screeners.base import CandidateContext
from services.scan_decomposition import DecomposedScanScore
from services.scan_history_config import ScanStage, resolve_history_policy
from services.scan_manager import ScanManager
from services.scan_scoring import ScanScoreOutcome
from services.scan_skip_reasons import (
    FALLBACK_NONE,
    FALLBACK_STRICT_FILTERS_REJECTED_ALL,
    INSUFFICIENT_HISTORY,
    classify_scan_fallback_reason,
    is_provider_limited_fallback,
)
from services.stage_a_ranking import StageACandidate, StageARankingResult


def _ohlc(*, bars: int, base: float = 2.5) -> pd.DataFrame:
    dates = pd.date_range("2025-06-01", periods=bars, freq="B")
    closes = [base + (i % 7) * 0.01 for i in range(bars)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.05 for c in closes],
            "low": [c - 0.05 for c in closes],
            "close": closes,
            "volume": [2_000_000] * bars,
        }
    )


def _penny_ctx(symbol: str, bars: int) -> CandidateContext:
    hist = _ohlc(bars=bars)
    price = float(hist["close"].iloc[-1])
    return CandidateContext(
        symbol=symbol.upper(),
        price=price,
        info={
            "currentPrice": price,
            "marketCap": 80_000_000,
            "averageVolume": 2_000_000,
            "exchange": "NYSE",
            "_reconcile_quality": 85.0,
        },
        fundamentals={},
        history=hist,
    )


def test_dq_boundary_against_penny_policy_min():
    policy = resolve_history_policy(Bucket.penny, ScanStage.STAGE_B)
    min_bars = policy.minimum_required_bars
    assert min_bars == 80

    excl_lo, _ = should_exclude_low_quality(85.0, min_bars - 1, min_bars=min_bars)
    excl_eq, _ = should_exclude_low_quality(85.0, min_bars, min_bars=min_bars)
    excl_hi, _ = should_exclude_low_quality(85.0, min_bars + 1, min_bars=min_bars)
    assert excl_lo is True
    assert excl_eq is False
    assert excl_hi is False


def test_gate_accepts_160_bar_penny_frame_rejects_79():
    policy = resolve_history_policy(Bucket.penny, ScanStage.STAGE_B)
    screener = MagicMock()
    screener.hard_filter.return_value = True
    options = ScanOptions()

    with patch("data.quality_filters.is_likely_delisted", return_value=False):
        ok_ctx = _penny_ctx("OK160", 160)
        ok = evaluate_stage_b_gate(
            ctx=ok_ctx,
            symbol="OK160",
            bucket=Bucket.penny,
            screener=screener,
            options=options,
            quality_score=85.0,
            hist_len=160,
            history_policy=policy,
        )
        assert ok.passed is True
        assert ok.history_policy_min_bars == 80

        short_ctx = _penny_ctx("SHORT79", 79)
        short = evaluate_stage_b_gate(
            ctx=short_ctx,
            symbol="SHORT79",
            bucket=Bucket.penny,
            screener=screener,
            options=options,
            quality_score=85.0,
            hist_len=79,
            history_policy=policy,
        )
    assert short.passed is False
    assert short.history_gate_exclusion is True
    assert short.skip_reason == INSUFFICIENT_HISTORY


def test_compounder_gate_still_requires_252():
    policy = resolve_history_policy(Bucket.compounder, ScanStage.STAGE_B)
    assert policy.minimum_required_bars == 252
    screener = MagicMock()
    screener.hard_filter.return_value = True
    options = ScanOptions()
    ctx = _penny_ctx("CMP200", 200)
    ctx.info["marketCap"] = 5_000_000_000
    result = evaluate_stage_b_gate(
        ctx=ctx,
        symbol="CMP200",
        bucket=Bucket.compounder,
        screener=screener,
        options=options,
        quality_score=85.0,
        hist_len=200,
        history_policy=policy,
    )
    assert result.passed is False
    assert result.history_gate_exclusion is True


def test_fallback_classifier_does_not_blame_provider_for_filter_rejects():
    reason = classify_scan_fallback_reason(
        published_normal_pool=False,
        partial_universe=False,
        provider_requested=0,
        provider_received=0,
        skipped=[
            {"symbol": "A", "reason": "strict_filter_rejection", "detail": "hard_filter"},
            {"symbol": "B", "reason": "strict_filter_rejection", "detail": "hard_filter"},
        ],
        history_gate_exclusion_count=0,
        used_fallback_candidates=True,
    )
    assert reason == FALLBACK_STRICT_FILTERS_REJECTED_ALL
    assert is_provider_limited_fallback(reason) is False
    assert (
        classify_scan_fallback_reason(
            published_normal_pool=True,
            partial_universe=False,
            provider_requested=0,
            provider_received=0,
            skipped=[],
            history_gate_exclusion_count=0,
            used_fallback_candidates=False,
        )
        == FALLBACK_NONE
    )


def test_db_cached_penny_scan_publishes_normal_pool_with_160_bar_frames():
    """E2E: 160-bar Stage A frames + lag-1 DB coverage must pass penny Stage B gate."""
    symbols = [f"P{i:02d}" for i in range(5)]
    bulk_hist = {sym: _ohlc(bars=160, base=2.0 + i * 0.1) for i, sym in enumerate(symbols)}
    manager = ScanManager()
    job = manager.create_job(Bucket.penny)
    saved: dict = {}

    mock_screener = MagicMock()
    mock_screener.hard_filter.return_value = True

    def _to_result(ctx, score, signals, risk, summary, metrics, **kwargs):
        return StockResult(
            symbol=str(ctx.symbol),
            price=float(ctx.price),
            score=float(score),
            bucket=Bucket.penny,
            risk_level=risk,
            summary=summary or "ok",
            signals=list(signals or []),
            metrics=dict(metrics or {}),
        )

    mock_screener.to_result.side_effect = _to_result

    def _score_outcome(**kwargs):
        return ScanScoreOutcome(
            score=72.0,
            signals=[],
            risk=RiskLevel.high,
            summary="scored",
            metrics={
                "data_quality_score": 85.0,
                "raw_score": 72.0,
                "relative_volume_ratio": 2.0,
                "average_dollar_volume_20d": 5_000_000.0,
            },
            raw_score=72.0,
            timings_ms={},
            legacy_invoked=False,
            engine_invoked=True,
            parity_sampled=False,
            parity_record=None,
        )

    with (
        patch("services.scan_pipeline.get_universe", return_value=symbols),
        patch("services.scan_pipeline.UNIVERSE_SCAN_BATCH_SIZE", 0),
        patch(
            "services.scan_pipeline.rank_stage_a_candidates",
            return_value=StageARankingResult(
                ranked=[
                    StageACandidate(
                        symbol=s.upper(),
                        pre_score=90.0 - i,
                        features={"mock": 90.0},
                        rank=i + 1,
                    )
                    for i, s in enumerate(symbols)
                ],
                excluded=[],
            ),
        ),
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
        patch("services.scan_pipeline.cache_module.get_latest_scan", return_value=None),
        patch.object(manager, "_get_screener", return_value=mock_screener),
        patch("services.scan_pipeline.PriceService") as ps_cls,
        patch("services.scan_scoring.score_stage_b_candidate", side_effect=_score_outcome),
        patch(
            "services.scan_pipeline.enrich_scan_display",
            side_effect=lambda info, fund, hist, metrics, legacy_summary="": (
                legacy_summary,
                metrics,
            ),
        ),
        patch(
            "services.scan_pipeline.build_decomposed_scores",
            return_value=DecomposedScanScore(
                alpha_score=70.0,
                confidence_score=65.0,
                tradability_score=60.0,
                ranking_score=68.0,
            ),
        ),
        patch(
            "services.scan_pipeline.attach_trade_hint_to_metrics",
            side_effect=lambda metrics, **kw: metrics,
        ),
        patch("data.quality_filters.is_likely_delisted", return_value=False),
        patch("data.candidate_gate.apply_quality_filters") as qf_patch,
    ):
        from data.quality_filters import QualityFilterResult

        qf_patch.return_value = QualityFilterResult(passed=True, reasons=[])
        ps = ps_cls.return_value

        def _download(*_a, **_k):
            ps.last_batch_meta = {
                "requested": len(symbols),
                "received": len(symbols),
                "coverage": 1.0,
                "source": "db",
                "partial": False,
                "database_hits": len(symbols),
                "provider_requested": 0,
                "provider_received": 0,
                "availability_coverage": 1.0,
                "live_refresh_coverage": 1.0,
                "lag_0_symbols": 0,
                "lag_1_symbols": len(symbols),
                "stale_symbols": 0,
            }
            return bulk_hist

        ps.download_batch.side_effect = _download
        ps.get_info.side_effect = lambda sym: {
            "currentPrice": 2.5,
            "marketCap": 80_000_000,
            "averageVolume": 2_000_000,
            "exchange": "NYSE",
        }
        ps.get_spy_history.return_value = None
        reg_cls.return_value.get_active.return_value = MagicMock(version_id="test-v1")
        options = MagicMock(max_results=25, mode="deep")
        options.model_dump.return_value = {"max_results": 25, "mode": "deep"}
        manager.run_scan(job.job_id, options)

    finished = manager.get_job(job.job_id)
    assert finished.status == ScanStatus.completed
    assert len(finished.results) >= 1
    assert all(not r.metrics.get("provider_limited_partial_data") for r in finished.results)
    meta = saved.get("metadata") or {}
    assert meta.get("fallback_reason") == FALLBACK_NONE
    assert meta.get("stage_b_minimum_required_bars") == 80
    assert meta.get("stage_a_returned_bar_limit") == 160
    cov = meta.get("coverage_diagnostics") or {}
    assert cov.get("provider_requested") == 0
    assert cov.get("database_hits") == len(symbols)
    assert cov.get("live_refresh_coverage") == 1.0
    assert finished.timings.get("stage_b_history_reloads") == 0.0
    assert finished.timings.get("stage_b_bulk_cache_hits") == float(len(symbols))
    call_kwargs = ps.download_batch.call_args.kwargs
    assert call_kwargs.get("min_bars") == 100
    assert call_kwargs.get("bar_limit") == 160
