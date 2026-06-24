"""Tests for Stage A → Stage B bulk history reuse."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.candidate_builder import HISTORY_SOURCE_BULK, HISTORY_SOURCE_PROVIDER, build_candidate
from data.price_service import PriceService
from models.schemas import Bucket
from models.schemas import Bucket
from services.scan_data_flow import ScanDataFlowMetrics
from services.scan_manager import _resolve_stage_b_context


def _make_history(*, bars: int = 120, base: float = 2.0) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=bars, freq="B")
    closes = [base + i * 0.02 for i in range(bars)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.05 for c in closes],
            "low": [c - 0.05 for c in closes],
            "close": closes,
            "volume": [1_500_000] * bars,
        }
    )


def test_build_candidate_skips_get_history_with_valid_preloaded_history():
    hist = _make_history()
    ps = MagicMock(spec=PriceService)
    ps.get_info.return_value = {"currentPrice": 2.0, "marketCap": 500_000_000}
    ps.get_spy_history.return_value = None

    ctx = build_candidate(
        "REUSE",
        reconcile=False,
        price_service=ps,
        history=hist,
        history_source=HISTORY_SOURCE_BULK,
    )

    assert ctx is not None
    ps.get_history.assert_not_called()
    assert ctx.info["_history_source"] == HISTORY_SOURCE_BULK
    assert ctx.info["_history_from_bulk_scan"] is True


def test_invalid_preloaded_history_triggers_one_provider_fallback():
    hist = _make_history(bars=5)
    loaded = _make_history(bars=120)
    ps = MagicMock(spec=PriceService)
    ps.get_info.return_value = {"currentPrice": 2.0, "marketCap": 500_000_000}
    ps.get_history.return_value = loaded
    ps.get_spy_history.return_value = None
    flow = ScanDataFlowMetrics()
    skipped: list[dict] = []

    ctx = _resolve_stage_b_context(
        "BAD",
        stage_b_period="6mo",
        stage_a_period="6mo",
        include_spy=False,
        price_service=ps,
        bulk_hist={"BAD": hist},
        skipped=skipped,
        flow=flow,
        bucket=Bucket.penny,
    )

    assert ctx is not None
    assert ps.get_history.call_count == 1
    assert flow.history_reload_count == 1
    assert flow.provider_fallbacks == 1
    assert ctx.info["_history_source"] == HISTORY_SOURCE_PROVIDER


def test_successful_candidate_does_not_fetch_history_twice():
    hist = _make_history()
    ps = MagicMock(spec=PriceService)
    ps.get_info.return_value = {"currentPrice": 2.0, "marketCap": 500_000_000}
    ps.get_history.return_value = hist
    ps.get_spy_history.return_value = None
    flow = ScanDataFlowMetrics()

    ctx = _resolve_stage_b_context(
        "GOOD",
        stage_b_period="6mo",
        stage_a_period="6mo",
        include_spy=False,
        price_service=ps,
        bulk_hist={"GOOD": hist},
        skipped=[],
        flow=flow,
        bucket=Bucket.penny,
    )

    assert ctx is not None
    ps.get_history.assert_not_called()
    assert flow.candidate_build_calls == 1
    assert flow.bulk_cache_hits == 1
    assert flow.history_reload_count == 0


def test_preloaded_and_loaded_candidates_match():
    hist = _make_history()
    ps = MagicMock(spec=PriceService)
    ps.get_info.return_value = {"currentPrice": 2.0, "marketCap": 500_000_000}
    ps.get_history.return_value = hist
    ps.get_spy_history.return_value = None

    preloaded = build_candidate(
        "PARITY",
        reconcile=False,
        price_service=ps,
        history=hist,
        history_source=HISTORY_SOURCE_BULK,
    )
    ps.get_history.reset_mock()
    loaded = build_candidate("PARITY", reconcile=False, price_service=ps)

    assert preloaded is not None and loaded is not None
    assert preloaded.price == loaded.price
    assert float(preloaded.history["close"].iloc[-1]) == float(loaded.history["close"].iloc[-1])
    assert len(preloaded.history) == len(loaded.history)


def test_bulk_history_dataframe_is_not_mutated():
    hist = _make_history()
    original_last = float(hist["close"].iloc[-1])
    original_len = len(hist)
    ps = MagicMock(spec=PriceService)
    ps.get_info.return_value = {"currentPrice": 2.0, "marketCap": 500_000_000}
    ps.get_spy_history.return_value = None

    ctx = build_candidate(
        "IMMUT",
        reconcile=False,
        price_service=ps,
        history=hist,
        history_source=HISTORY_SOURCE_BULK,
    )

    assert ctx is not None
    assert float(hist["close"].iloc[-1]) == original_last
    assert len(hist) == original_len
    assert ctx.history is not hist


def test_scan_history_reuse_benchmark_fewer_provider_calls():
    """Synthetic benchmark: bulk reuse eliminates per-symbol get_history calls."""
    symbols = [f"S{i:02d}" for i in range(10)]
    bulk_hist = {sym: _make_history(base=2.0 + i * 0.1) for i, sym in enumerate(symbols)}

    def _old_path() -> tuple[int, float]:
        ps = MagicMock(spec=PriceService)
        ps.get_info.return_value = {"currentPrice": 2.0, "marketCap": 500_000_000}
        ps.get_history.side_effect = lambda sym, period="6mo", **kw: bulk_hist[sym.upper()]
        ps.get_spy_history.return_value = None
        started = time.perf_counter()
        for sym in symbols:
            build_candidate(sym, reconcile=False, price_service=ps)
        return ps.get_history.call_count, time.perf_counter() - started

    def _new_path() -> tuple[int, float]:
        ps = MagicMock(spec=PriceService)
        ps.get_info.return_value = {"currentPrice": 2.0, "marketCap": 500_000_000}
        ps.get_spy_history.return_value = None
        flow = ScanDataFlowMetrics()
        started = time.perf_counter()
        for sym in symbols:
            _resolve_stage_b_context(
                sym,
                stage_b_period="6mo",
                stage_a_period="6mo",
                include_spy=False,
                price_service=ps,
                bulk_hist=bulk_hist,
                skipped=[],
                flow=flow,
                bucket=Bucket.penny,
            )
        return flow.history_reload_count, time.perf_counter() - started

    old_calls, old_duration = _old_path()
    new_calls, new_duration = _new_path()

    assert old_calls == len(symbols)
    assert new_calls == 0

    # Expose benchmark numbers for manual inspection when this test runs.
    print(
        f"BENCHMARK history_calls before={old_calls} after={new_calls} "
        f"duration_before_ms={old_duration * 1000:.2f} duration_after_ms={new_duration * 1000:.2f}"
    )
