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
        ps_cls.return_value.download_batch.return_value = bulk_hist

        if use_engine:
            stack.enter_context(
                patch("services.scan_scoring.ScoringEngine.score", side_effect=_engine_score)
            )
            stack.enter_context(patch("config.USE_SCORING_ENGINE_IN_SCAN", True))

        reg_cls.return_value.get_active.return_value = SimpleNamespace(version_id="test-integration-v1")
        options = MagicMock()
        options.max_results = max_results
        options.model_dump.return_value = {"max_results": max_results}
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
    assert saved["metadata"] is None


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
