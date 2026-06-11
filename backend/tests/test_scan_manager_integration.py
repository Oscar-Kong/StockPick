"""Integration tests for ScanManager.run_scan — Stage A → Stage B → rank → cache."""
from __future__ import annotations

import sys
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "ta" not in sys.modules:
    _ta = MagicMock()
    sys.modules["ta"] = _ta
    sys.modules["ta.momentum"] = _ta.momentum
    sys.modules["ta.trend"] = _ta.trend
    sys.modules["ta.volatility"] = _ta.volatility

from data.quality_filters import QualityFilterResult
from models.schemas import Bucket, RiskLevel, ScanStatus
from screeners.base import CandidateContext, WeightedSignal
from services.scan_manager import ScanManager


def _make_history(symbol: str, *, base: float = 10.0) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=60, freq="B")
    closes = [base + i * 0.05 for i in range(60)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.2 for c in closes],
            "low": [c - 0.2 for c in closes],
            "close": closes,
            "volume": [1_500_000] * 60,
        }
    )


def _make_ctx(symbol: str, *, base: float = 10.0) -> CandidateContext:
    history = _make_history(symbol, base=base)
    return CandidateContext(
        symbol=symbol.upper(),
        price=float(history["close"].iloc[-1]),
        info={"sector": "Technology", "marketCap": 5_000_000_000, "_reconcile_quality": 85.0},
        fundamentals={},
        history=history,
    )


def _mock_screener(bucket: Bucket, score_map: dict[str, float]) -> MagicMock:
    screener = MagicMock()
    screener.bucket = bucket

    def _score(ctx: CandidateContext):
        sym = ctx.symbol.upper()
        val = score_map.get(sym, 65.0)
        signals = [WeightedSignal(f"Signal {sym}", val, 1.0, "mock")]
        return val, signals, RiskLevel.medium, f"Summary {sym}", {"raw_score": val}

    screener.score.side_effect = _score
    screener.enrich.side_effect = lambda sym: _make_ctx(sym, base=score_map.get(sym.upper(), 65.0))
    screener.hard_filter.return_value = True
    screener.to_result.side_effect = (
        lambda ctx, score, signals, risk, summary, metrics: MagicMock(
            symbol=ctx.symbol,
            score=round(score, 1),
            signals=signals,
            risk_level=risk,
            summary=summary,
            metrics=metrics,
            model_dump=lambda mode="json": {
                "symbol": ctx.symbol,
                "price": ctx.price,
                "score": round(score, 1),
                "signals": [],
                "risk_level": risk.value if hasattr(risk, "value") else risk,
                "summary": summary,
                "bucket": bucket.value,
                "metrics": metrics,
            },
        )
    )
    return screener


def _mock_scoring_result(*, final: float) -> SimpleNamespace:
    factors = [
        SimpleNamespace(
            factor_id="test_factor",
            display_name="Engine",
            norm_score=final,
            weight=1.0,
            contribution=final,
            description="engine",
        )
    ]
    return SimpleNamespace(
        sleeve="medium",
        signals=[WeightedSignal("Engine", final, 1.0, "engine")],
        factors=factors,
        raw_score=final,
        score_after_regime=final,
        regime_mult=1.0,
        sector_tilt=0.0,
        dq_multiplier=1.0,
        score_after_dq=final,
        openbb_delta=0.0,
        score_after_openbb=final,
        final_score=final,
        risk_level=RiskLevel.medium,
        summary="Engine summary",
        metrics={"regime": {}},
    )


def _run_scan_with_mocks(
    *,
    bucket: Bucket,
    universe: list[str],
    stage_a_symbols: list[str],
    score_map: dict[str, float],
    max_results: int = 25,
    use_engine: bool = False,
    engine_scores: dict[str, float] | None = None,
    mode: str = "deep",
    stage_b_top_n: int = 50,
    stage_b_top_n_fast: int = 15,
    download_side_effect=None,
):
    manager = ScanManager()
    job = manager.create_job(bucket)
    bulk_hist = {sym.upper(): _make_history(sym, base=score_map.get(sym.upper(), 10.0)) for sym in universe}
    mock_screener = _mock_screener(bucket, score_map)
    saved: dict = {}

    def _capture_save(bucket_name, results, completed_at, ttl, strategy_version=None, metadata=None):
        saved["bucket"] = bucket_name
        saved["results"] = results
        saved["completed_at"] = completed_at
        saved["ttl"] = ttl
        saved["strategy_version"] = strategy_version
        saved["metadata"] = metadata

    engine_scores = engine_scores or score_map

    def _engine_score(ctx, sleeve, **kwargs):
        sym = ctx.symbol.upper()
        final = engine_scores.get(sym, 60.0)
        return _mock_scoring_result(final=final)

    with ExitStack() as stack:
        stack.enter_context(patch("services.scan_manager.get_universe", return_value=[s.upper() for s in universe]))
        stack.enter_context(patch("services.scan_manager.UNIVERSE_SCAN_BATCH_SIZE", 0))
        stack.enter_context(patch("services.scan_manager.SCAN_STAGE_B_TOP_N", stage_b_top_n))
        stack.enter_context(patch("services.scan_manager.SCAN_STAGE_B_TOP_N_FAST", stage_b_top_n_fast))
        stack.enter_context(
            patch(
                "services.scan_manager.filter_universe_by_price",
                return_value=[s.upper() for s in stage_a_symbols],
            )
        )
        stack.enter_context(patch("services.scan_manager.should_exclude_low_quality", return_value=(False, "")))
        stack.enter_context(
            patch(
                "services.scan_manager.apply_quality_filters",
                return_value=QualityFilterResult(passed=True, reasons=[]),
            )
        )
        stack.enter_context(
            patch(
                "services.scan_manager.enrich_scan_display",
                side_effect=lambda info, fund, hist, metrics, legacy_summary="": (legacy_summary, metrics),
            )
        )
        stack.enter_context(patch("services.scan_manager.HistoricalStore"))
        reg_cls = stack.enter_context(patch("services.scan_manager.StrategyRegistry"))
        stack.enter_context(
            patch("services.scan_manager.cache_module.save_scan_results", side_effect=_capture_save)
        )
        stack.enter_context(patch("services.scan_manager.cache_module.save_scan_snapshot"))
        attempt_marker: dict = {}

        def _record_failure(bucket_name, error, *, ttl_seconds=3600.0):
            attempt_marker["bucket"] = bucket_name
            attempt_marker["error"] = error
            attempt_marker["ttl"] = ttl_seconds

        def _clear_failure(bucket_name):
            attempt_marker["cleared_for"] = bucket_name

        stack.enter_context(
            patch("services.scan_manager.cache_module.record_scan_attempt_failure", side_effect=_record_failure)
        )
        stack.enter_context(
            patch("services.scan_manager.cache_module.clear_scan_attempt_failure", side_effect=_clear_failure)
        )
        saved["_attempt_marker"] = attempt_marker
        stack.enter_context(patch.object(manager, "_get_screener", return_value=mock_screener))
        stack.enter_context(patch("services.scan_scoring.USE_SCORING_ENGINE_IN_SCAN", use_engine))
        stack.enter_context(patch("services.scan_scoring.PERSIST_SCORE_ATTRIBUTION", False))
        stack.enter_context(
            patch(
                "services.scan_scoring.enrich_metrics",
                side_effect=lambda sym, info, fund, m, bucket, **kw: {**m, "enriched": True},
            )
        )
        stack.enter_context(
            patch("services.scan_scoring._apply_openbb_adjustment", side_effect=lambda score, metrics: score)
        )
        ps_cls = stack.enter_context(patch("services.scan_manager.PriceService"))
        if download_side_effect is not None:
            ps_cls.return_value.download_batch.side_effect = download_side_effect
        else:
            ps_cls.return_value.download_batch.return_value = bulk_hist

        if use_engine:
            stack.enter_context(
                patch("services.scan_scoring.ScoringEngine.score", side_effect=_engine_score)
            )
            stack.enter_context(patch("config.USE_SCORING_ENGINE_IN_SCAN", True))

        reg_cls.return_value.get_active.return_value = SimpleNamespace(version_id="test-integration-v1")
        options = MagicMock()
        options.max_results = max_results
        options.mode = mode
        options.model_dump.return_value = {"max_results": max_results, "mode": mode}
        manager.run_scan(job.job_id, options)

    finished = manager.get_job(job.job_id)
    return finished, mock_screener, saved


def test_stage_a_filters_stage_b_symbols():
    universe = ["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON"]
    stage_a = ["ALPHA", "BETA", "GAMMA"]
    score_map = {"ALPHA": 70.0, "BETA": 85.0, "GAMMA": 60.0}

    job, screener, _saved = _run_scan_with_mocks(
        bucket=Bucket.medium,
        universe=universe,
        stage_a_symbols=stage_a,
        score_map=score_map,
        max_results=25,
    )

    assert job.status == ScanStatus.completed
    assert screener.enrich.call_count == len(stage_a)
    enriched = {c.args[0].upper() for c in screener.enrich.call_args_list}
    assert enriched == {s.upper() for s in stage_a}


def test_stage_b_ranking_and_max_results_truncation():
    stage_a = ["HIGH", "MID", "LOW"]
    score_map = {"HIGH": 92.0, "MID": 78.0, "LOW": 55.0}

    job, _screener, saved = _run_scan_with_mocks(
        bucket=Bucket.medium,
        universe=stage_a,
        stage_a_symbols=stage_a,
        score_map=score_map,
        max_results=2,
    )

    assert job.status == ScanStatus.completed
    assert len(job.results) == 2
    scores = [r.score for r in job.results]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 92.0
    assert scores[1] == 78.0
    # Metadata is no longer None when the engine is disabled — the job always
    # records its timings so the UI can render stage A/B durations.
    metadata = saved["metadata"]
    assert metadata is not None
    assert "scoring_engine_used" not in metadata
    assert "parity_summary" not in metadata
    assert "timings" in metadata
    assert metadata["timings"]["stage_b_candidates"] == 3.0


def test_cache_metadata_and_parity_summary_when_engine_enabled():
    stage_a = ["ENG1", "ENG2"]
    legacy_scores = {"ENG1": 72.0, "ENG2": 68.0}
    engine_scores = {"ENG1": 58.0, "ENG2": 62.0}

    job, _screener, saved = _run_scan_with_mocks(
        bucket=Bucket.medium,
        universe=stage_a,
        stage_a_symbols=stage_a,
        score_map=legacy_scores,
        max_results=25,
        use_engine=True,
        engine_scores=engine_scores,
    )

    assert job.status == ScanStatus.completed
    assert job.parity_summary is not None
    assert job.parity_summary["symbol_count"] == 2
    assert job.parity_summary["average_delta"] >= 0
    assert job.parity_summary["scoring_engine_used"] is True
    assert len(job.parity_summary["records"]) == 2

    metadata = saved.get("metadata")
    assert metadata is not None
    assert metadata["scoring_engine_used"] is True
    assert metadata["parity_summary"]["symbol_count"] == 2
    assert "ScoringEngine" in (job.message or "")


def test_scan_records_stage_a_and_stage_b_timings():
    """The scan job must publish stage A and stage B durations so the UI can
    render timing badges and ops can spot slow provider fetches."""
    stage_a = ["A1", "A2", "A3"]
    job, _screener, saved = _run_scan_with_mocks(
        bucket=Bucket.medium,
        universe=stage_a,
        stage_a_symbols=stage_a,
        score_map={"A1": 70.0, "A2": 60.0, "A3": 55.0},
        max_results=25,
    )
    assert job.status == ScanStatus.completed
    assert "stage_a_ms" in job.timings
    assert "stage_b_ms" in job.timings
    assert "total_ms" in job.timings
    assert job.timings["stage_b_candidates"] == 3.0
    # Persisted scan cache must include the timings so /scan/latest/{bucket}
    # can echo them to the frontend after a backend restart.
    assert saved["metadata"]["timings"]["stage_b_candidates"] == 3.0


def test_scan_options_fast_mode_caps_stage_b_at_fast_top_n():
    """`mode=fast` must cut Stage B candidate count to SCAN_STAGE_B_TOP_N_FAST.

    This is the smallest unit of work that proves the new env knob is wired
    through ScanOptions → run_scan without changing legacy "deep" behavior.
    """
    stage_a = [f"SYM{i:02d}" for i in range(20)]  # 20 candidates passing Stage A
    score_map = {sym: 70.0 - i * 0.5 for i, sym in enumerate(stage_a)}

    job, screener, _saved = _run_scan_with_mocks(
        bucket=Bucket.medium,
        universe=stage_a,
        stage_a_symbols=stage_a,
        score_map=score_map,
        max_results=25,
        mode="fast",
        stage_b_top_n=50,
        stage_b_top_n_fast=5,
    )
    assert job.status == ScanStatus.completed
    # Only the top 5 (by Stage A order) should reach the deep-scoring path.
    assert screener.enrich.call_count == 5


def test_scan_options_deep_mode_uses_stage_b_top_n():
    stage_a = [f"D{i:02d}" for i in range(8)]
    score_map = {sym: 60.0 for sym in stage_a}
    job, screener, _saved = _run_scan_with_mocks(
        bucket=Bucket.medium,
        universe=stage_a,
        stage_a_symbols=stage_a,
        score_map=score_map,
        mode="deep",
        stage_b_top_n=6,
        stage_b_top_n_fast=2,
    )
    assert job.status == ScanStatus.completed
    assert screener.enrich.call_count == 6


def test_compounder_scan_uses_long_ttl():
    """Per-bucket TTL: compounder should write with SCAN_RESULT_TTL_COMPOUNDER,
    which is much longer than the default penny TTL because fundamentals do
    not change intra-day."""
    from config import SCAN_RESULT_TTL_COMPOUNDER, SCAN_RESULT_TTL_PENNY

    _job, _screener, saved = _run_scan_with_mocks(
        bucket=Bucket.compounder,
        universe=["CMP1"],
        stage_a_symbols=["CMP1"],
        score_map={"CMP1": 80.0},
    )
    assert saved["ttl"] == SCAN_RESULT_TTL_COMPOUNDER

    _job2, _screener2, saved2 = _run_scan_with_mocks(
        bucket=Bucket.penny,
        universe=["PNY1"],
        stage_a_symbols=["PNY1"],
        score_map={"PNY1": 70.0},
    )
    assert saved2["ttl"] == SCAN_RESULT_TTL_PENNY


def test_failed_scan_records_attempt_marker_without_touching_latest():
    """When run_scan raises, we must NOT clobber `scan:latest:{bucket}` but
    we MUST stamp a `scan:last_attempt:{bucket}` marker so the route can
    show "last attempt failed" alongside the prior successful results."""

    def _boom(symbols, period, max_runtime_seconds):
        raise RuntimeError("synthetic provider failure")

    job, _screener, saved = _run_scan_with_mocks(
        bucket=Bucket.penny,
        universe=["PNY1", "PNY2"],
        stage_a_symbols=["PNY1", "PNY2"],
        score_map={"PNY1": 70.0, "PNY2": 60.0},
        download_side_effect=_boom,
    )
    assert job.status == ScanStatus.failed
    # `latest` must not be overwritten by a failed run.
    assert "results" not in saved
    # The failure-attempt marker must be recorded for /scan/latest/{bucket}.
    attempt = saved["_attempt_marker"]
    assert attempt.get("bucket") == "penny"
    assert "synthetic provider failure" in (attempt.get("error") or "")


def test_successful_scan_clears_prior_failure_marker():
    job, _screener, saved = _run_scan_with_mocks(
        bucket=Bucket.penny,
        universe=["PNY1"],
        stage_a_symbols=["PNY1"],
        score_map={"PNY1": 70.0},
    )
    assert job.status == ScanStatus.completed
    assert saved["_attempt_marker"].get("cleared_for") == "penny"
