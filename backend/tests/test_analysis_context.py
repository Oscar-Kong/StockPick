"""Tests for shared AnalysisContext, snapshot/core helpers, and matrix SPY hoist."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.analysis_context import (
    AnalysisTimings,
    build_analysis_delta,
    build_trade_plan,
    single_flight,
)


def test_single_flight_dedupes_concurrent_calls():
    import threading
    import time
    import uuid

    started = threading.Event()
    release = threading.Event()
    calls = {"n": 0}
    key = f"test:key:{uuid.uuid4().hex}"

    def work():
        calls["n"] += 1
        started.set()
        release.wait(timeout=5)
        return "ok"

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(single_flight, key, work) for _ in range(8)]
        assert started.wait(5)
        time.sleep(0.05)
        release.set()
        results = [f.result(timeout=5) for f in futs]

    assert results == ["ok"] * 8
    assert calls["n"] == 1


def test_build_trade_plan_penny_from_sizing():
    class Rec:
        recommendation = "Buy"
        confidence = 72
        time_horizon_days = 3
        expected_return_pct = 8.0
        expected_downside_pct = -4.0
        bull_case = "Volume surge"
        bear_case = "Fails breakout"
        data_confidence = MagicMock(data_confidence=80)

    class Sizing:
        stop_loss_pct = 5.0
        recommended_weight_pct = 2.5
        max_weight_pct = 5.0

    class V2:
        sleeve = "penny"
        recommendation = Rec()
        position_sizing = Sizing()
        metrics = {}
        valuation = None

    base = {
        "assigned_bucket": "penny",
        "price": 2.0,
        "metrics": {"relative_volume": 3.2},
        "alerts": [{"message": "Wide spread"}],
        "fundamentals": {},
    }
    plan = build_trade_plan(base, V2())
    assert plan["sleeve"] == "penny"
    assert plan["initial_stop"] == pytest.approx(1.9, rel=1e-3)
    assert plan["target_1"] is not None
    assert plan["risk_reward"] is not None
    assert "Wide spread" in plan["invalidation"]


def test_build_trade_plan_dedupes_invalidation():
    class Rec:
        recommendation = "Avoid"
        confidence = 40
        time_horizon_days = 5
        expected_return_pct = 2.0
        expected_downside_pct = -8.0
        bull_case = "Bounce"
        bear_case = "Low cross-source agreement — verify manually"
        data_confidence = MagicMock(data_confidence=17)

    class V2:
        sleeve = "penny"
        recommendation = Rec()
        position_sizing = None
        metrics = {}
        valuation = None

    base = {
        "assigned_bucket": "penny",
        "price": 4.5,
        "metrics": {},
        "alerts": [
            {"message": "Low cross-source agreement — verify manually"},
            {"message": "Low data quality (17%)"},
        ],
        "fundamentals": {},
    }
    plan = build_trade_plan(base, V2())
    assert plan["invalidation"] == [
        "Low cross-source agreement — verify manually",
        "Low data quality (17%)",
    ]


def test_build_analysis_delta_detects_score_change():
    prev = {
        "updated_at": "2026-01-01T00:00:00Z",
        "payload": {
            "score": 60,
            "price": 2.0,
            "risk_level": "high",
            "metrics": {"recommendation": "Watch"},
        },
    }

    class Rec:
        recommendation = "Buy"

    class V2:
        score = 74
        risk_level = "medium"
        recommendation = Rec()

    delta = build_analysis_delta({"score": 74, "price": 2.1, "risk_level": "medium"}, V2(), prev)
    assert delta is not None
    assert delta["score"]["from"] == 60
    assert delta["score"]["to"] == 74
    assert any(c["field"] == "recommendation" for c in delta["changes"])


def test_analysis_timings_server_timing_header():
    t = AnalysisTimings()
    t.stages["cache_lookup"] = 1.5
    t.stages["v2_score"] = 120.0
    header = t.server_timing_header()
    assert "cache_lookup;dur=1.5" in header
    assert "v2_score;dur=120.0" in header


def test_quick_technicals_accepts_shared_spy():
    from services.analyze_service import _quick_technicals_from_hist

    idx = pd.date_range("2024-01-01", periods=60, freq="B")
    hist = pd.DataFrame(
        {
            "date": idx,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": [1.0 + i * 0.01 for i in range(60)],
            "volume": 1_000_000,
        }
    )
    spy = hist.copy()
    spy["close"] = [1.0 + i * 0.005 for i in range(60)]
    out = _quick_technicals_from_hist(hist, spy)
    assert "trend_score" in out
    assert out["price"] is not None


def test_watchlist_matrix_loads_spy_once():
    from services.analyze_service import build_watchlist_matrix

    spy_calls = {"n": 0}

    class FakeStore:
        def get_quotes(self, symbol, limit=280):
            if symbol == "SPY":
                spy_calls["n"] += 1
            idx = pd.date_range("2024-01-01", periods=80, freq="B")
            return [
                {
                    "date": d.to_pydatetime(),
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.0 + i * 0.01,
                    "volume": 1e6,
                }
                for i, d in enumerate(idx)
            ]

    class FakePS:
        store = FakeStore()

    items = [
        {"symbol": "AAA", "bucket": "penny", "score": 50, "notes": ""},
        {"symbol": "BBB", "bucket": "penny", "score": 60, "notes": ""},
        {"symbol": "CCC", "bucket": "compounder", "score": 70, "notes": ""},
    ]

    with (
        patch("services.analyze_service.cache_module.get_watchlist", return_value=items),
        patch("services.analyze_service.PriceService", return_value=FakePS()),
        patch("services.analyze_service.Cache") as mock_cache,
        patch("services.analyze_service.get_cached_watchlist_matrix", return_value=None),
        patch("services.analyze_service.compute_alerts", return_value=[]),
    ):
        mock_cache.return_value.get.return_value = None
        mock_cache.return_value.set = MagicMock()
        rows = build_watchlist_matrix(force_refresh=True)

    assert len(rows) == 3
    assert spy_calls["n"] == 1


def test_v2_score_route_defaults_parity_off():
    from api.routes_v2 import get_v2_score
    import inspect

    sig = inspect.signature(get_v2_score)
    parity_default = sig.parameters["validate_parity"].default
    persist_default = sig.parameters["persist_snapshot"].default
    assert getattr(parity_default, "default", parity_default) is False
    assert getattr(persist_default, "default", persist_default) is False
