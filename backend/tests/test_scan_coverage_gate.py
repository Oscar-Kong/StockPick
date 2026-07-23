"""Scan pipeline preserves last complete latest when bulk coverage is low."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas import Bucket, ScanStatus
from services.scan_manager import ScanManager
from services.stage_a_ranking import StageACandidate, StageARankingResult


def _hist() -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=30, freq="B")
    return pd.DataFrame(
        {
            "date": dates,
            "open": [5.0] * 30,
            "high": [5.5] * 30,
            "low": [4.5] * 30,
            "close": [5.2] * 30,
            "volume": [500_000] * 30,
        }
    )


def test_partial_universe_skips_save_latest():
    manager = ScanManager()
    job = manager.create_job(Bucket.penny)
    universe = [f"S{i}" for i in range(10)]
    bulk_hist = {"S0": _hist()}
    save_calls: list = []

    with (
        patch("services.scan_pipeline.get_universe", return_value=universe),
        patch("services.scan_pipeline.UNIVERSE_SCAN_BATCH_SIZE", 0),
        patch("services.scan_pipeline.SCAN_BULK_COVERAGE_MIN", 0.70),
        patch(
            "services.scan_pipeline.rank_stage_a_candidates",
            return_value=StageARankingResult(
                ranked=[
                    StageACandidate(symbol="S0", pre_score=90.0, features={}, rank=1),
                ],
                excluded=[],
            ),
        ),
        patch("services.scan_pipeline.build_candidate", return_value=None),
        patch("services.scan_pipeline.StrategyRegistry") as reg_cls,
        patch("services.scan_pipeline.HistoricalStore"),
        patch(
            "services.scan_pipeline.cache_module.save_scan_results",
            side_effect=lambda *a, **k: save_calls.append("latest"),
        ),
        patch(
            "services.scan_pipeline.cache_module.save_scan_snapshot",
            side_effect=lambda *a, **k: save_calls.append("snap"),
        ),
        patch("services.scan_pipeline.cache_module.clear_scan_attempt_failure"),
        patch.object(manager, "_get_screener", return_value=MagicMock()),
        patch("services.scan_pipeline.PriceService") as ps_cls,
    ):
        ps = ps_cls.return_value
        ps.download_batch.return_value = bulk_hist
        ps.last_batch_meta = {
            "requested": 10,
            "received": 1,
            "missing_count": 9,
            "coverage": 0.1,
            "source": "yfinance",
            "partial": True,
        }
        reg_cls.return_value.get_active.return_value = MagicMock(version_id="test-v1")
        options = MagicMock(max_results=25, mode="deep")
        options.model_dump.return_value = {"max_results": 25, "mode": "deep"}
        manager.run_scan(job.job_id, options)

    finished = manager.get_job(job.job_id)
    assert finished.status == ScanStatus.completed
    assert "Partial universe" in (finished.message or "")
    assert save_calls == []


def test_full_coverage_still_saves_latest():
    manager = ScanManager()
    job = manager.create_job(Bucket.penny)
    universe = ["AAA", "BBB"]
    hist = _hist()
    bulk_hist = {"AAA": hist, "BBB": hist}
    save_calls: list = []

    with (
        patch("services.scan_pipeline.get_universe", return_value=universe),
        patch("services.scan_pipeline.UNIVERSE_SCAN_BATCH_SIZE", 0),
        patch("services.scan_pipeline.SCAN_BULK_COVERAGE_MIN", 0.70),
        patch(
            "services.scan_pipeline.rank_stage_a_candidates",
            return_value=StageARankingResult(ranked=[], excluded=[]),
        ),
        patch("services.scan_pipeline.StrategyRegistry") as reg_cls,
        patch("services.scan_pipeline.HistoricalStore"),
        patch(
            "services.scan_pipeline.cache_module.save_scan_results",
            side_effect=lambda *a, **k: save_calls.append("latest"),
        ),
        patch(
            "services.scan_pipeline.cache_module.save_scan_snapshot",
            side_effect=lambda *a, **k: save_calls.append("snap"),
        ),
        patch("services.scan_pipeline.cache_module.clear_scan_attempt_failure"),
        patch.object(manager, "_get_screener", return_value=MagicMock()),
        patch("services.scan_pipeline.PriceService") as ps_cls,
    ):
        ps = ps_cls.return_value
        ps.download_batch.return_value = bulk_hist
        ps.last_batch_meta = {
            "requested": 2,
            "received": 2,
            "missing_count": 0,
            "coverage": 1.0,
            "source": "yfinance",
            "partial": False,
        }
        reg_cls.return_value.get_active.return_value = MagicMock(version_id="test-v1")
        options = MagicMock(max_results=25, mode="deep")
        options.model_dump.return_value = {"max_results": 25, "mode": "deep"}
        manager.run_scan(job.job_id, options)

    finished = manager.get_job(job.job_id)
    assert finished.status == ScanStatus.completed
    assert "Partial universe" not in (finished.message or "")
    assert "latest" in save_calls
