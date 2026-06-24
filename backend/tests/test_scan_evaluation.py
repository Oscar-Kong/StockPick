"""Tests for offline scan evaluation harness."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "ta" not in sys.modules:
    _ta = MagicMock()
    sys.modules["ta"] = _ta
    sys.modules["ta.momentum"] = _ta.momentum
    sys.modules["ta.trend"] = _ta.trend
    sys.modules["ta.volatility"] = _ta.volatility

from models.schemas import Bucket
from services.scan_evaluation_metrics import (
    aggregate_ranking_quality,
    score_decile_breakdown,
    stage_a_recall_metrics,
)
from services.scan_evaluation_pit import (
    assert_no_lookahead,
    apply_penny_friction,
    forward_path_excursions,
    forward_return_pct,
    truncate_history,
)
from services.scan_evaluation_replay import ReplayConfig, replay_scan_date
from services.scan_evaluation_service import ScanEvaluationConfig, run_scan_evaluation


def _ohlc(
    n: int,
    *,
    start: str = "2024-01-02",
    step_pct: float = 0.002,
    base: float = 10.0,
) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=n)
    closes = [base]
    for _ in range(n - 1):
        closes.append(closes[-1] * (1.0 + step_pct))
    return pd.DataFrame(
        {
            "date": [d.date() for d in dates],
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [1_500_000] * n,
        }
    )


def _panel(symbols: list[str], *, step_pct: float = 0.002) -> dict[str, pd.DataFrame]:
    out = {}
    for i, sym in enumerate(symbols):
        out[sym] = _ohlc(120, start="2024-01-02", step_pct=step_pct + i * 0.0005, base=5.0 + i)
    return out


def test_truncate_history_no_future_leakage():
    hist = _ohlc(30)
    as_of = date(2024, 1, 15)
    trimmed = truncate_history(hist, as_of)
    assert not trimmed.empty
    assert trimmed["date"].max() <= as_of
    assert_no_lookahead(trimmed, as_of)
    with pytest.raises(ValueError, match="Look-ahead"):
        assert_no_lookahead(hist, date(2024, 1, 1))


def test_forward_return_window_correct():
    hist = _ohlc(80, step_pct=0.001)
    as_of = date(2024, 2, 1)
    r1 = forward_return_pct(hist, as_of, 1)
    r5 = forward_return_pct(hist, as_of, 5)
    assert r1 is not None
    assert r5 is not None
    assert r5 > r1  # upward drift


def test_forward_return_missing_trading_days():
    hist = _ohlc(25)
    as_of = date(2024, 2, 20)
    r60 = forward_return_pct(hist, as_of, 60)
    assert r60 is None


def test_mae_mfe_excursions():
    hist = _ohlc(60, step_pct=0.003)
    as_of = date(2024, 2, 1)
    exc = forward_path_excursions(hist, as_of, 5)
    assert exc["mae_pct"] is not None
    assert exc["mfe_pct"] is not None
    assert exc["mfe_pct"] >= exc["mae_pct"]


def test_penny_friction_reduces_return():
    assert apply_penny_friction(5.0, spread_bps=50, slippage_bps=25) == pytest.approx(4.25, abs=0.01)


def test_score_decile_breakdown():
    scores = list(range(10, 110, 10))
    fwd = [x * 0.01 for x in scores]
    out = score_decile_breakdown(scores, fwd, n_deciles=10)
    assert out["sufficient"] is True
    assert len(out["deciles"]) == 10
    assert out["top_minus_bottom_spread_pct"] > 0


def test_score_decile_insufficient_sample():
    out = score_decile_breakdown([1.0, 2.0], [0.1, 0.2], n_deciles=10)
    assert out["sufficient"] is False


def test_stage_a_recall_calculations():
    forward = {"AAA": 10.0, "BBB": 8.0, "CCC": 6.0, "DDD": 4.0, "EEE": 2.0, "FFF": 0.5}
    stage_a = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    out = stage_a_recall_metrics(
        stage_a_ranked=stage_a,
        forward_by_symbol=forward,
        stage_b_caps=[3, 6],
        recall_k_values=[3],
    )
    assert out["sufficient"] is True
    assert out["recall_at_k"]["3"] == pytest.approx(1.0)
    assert "AAA" not in out["high_return_excluded_by_stage_a"][:3]


@patch("services.scan_evaluation_replay.universe_for_date")
def test_replay_deterministic_ranking(mock_universe):
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    mock_universe.return_value = (symbols, "fallback")
    panel = _panel(symbols)
    cfg = ReplayConfig(
        bucket="penny",
        scan_date="2024-03-15",
        algorithm_version="alphabetical_baseline",
        max_results=5,
        forward_horizons=[5, 20],
        max_universe=10,
    )
    a = replay_scan_date(price_panel=panel, config=cfg)
    b = replay_scan_date(price_panel=panel, config=cfg)
    assert [c["symbol"] for c in a["candidates"]] == [c["symbol"] for c in b["candidates"]]
    assert [c["ranking_score"] for c in a["candidates"]] == [c["ranking_score"] for c in b["candidates"]]


@patch("services.scan_evaluation_replay.universe_for_date")
def test_replay_stage_a_v1_no_lookahead(mock_universe):
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    mock_universe.return_value = (symbols, "fallback")
    panel = _panel(symbols)
    cfg = ReplayConfig(
        bucket="penny",
        scan_date="2024-03-15",
        algorithm_version="stage_a_v1",
        stage_b_cap=4,
        max_results=4,
        forward_horizons=[5],
        max_universe=10,
    )
    snap = replay_scan_date(price_panel=panel, config=cfg)
    assert snap["final_count"] <= 4
    for c in snap["candidates"]:
        fo = c["forward_outcomes"]["5"]
        assert "forward_return_pct" in fo


@patch("services.scan_evaluation_replay.universe_for_date")
def test_replay_delisted_incomplete_symbol(mock_universe):
    symbols = ["GOOD", "SHORT"]
    mock_universe.return_value = (symbols, "fallback")
    panel = {
        "GOOD": _ohlc(100),
        "SHORT": _ohlc(15),
    }
    cfg = ReplayConfig(
        bucket="penny",
        scan_date="2024-02-01",
        algorithm_version="alphabetical_baseline",
        max_results=2,
        forward_horizons=[20, 60],
        max_universe=5,
    )
    snap = replay_scan_date(price_panel=panel, config=cfg)
    short_row = next(c for c in snap["candidates"] if c["symbol"] == "SHORT")
    assert short_row["forward_outcomes"]["60"]["delisted_or_incomplete"] is True


@patch("services.scan_evaluation_service.rebalance_dates")
@patch("services.scan_evaluation_replay.universe_for_date")
def test_run_evaluation_end_to_end(mock_universe, mock_rebalance):
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]
    mock_universe.return_value = (symbols, "fallback")
    mock_rebalance.return_value = [date(2024, 3, 1), date(2024, 4, 1)]
    panel = _panel(symbols)

    cfg = ScanEvaluationConfig(
        bucket="penny",
        start_date="2024-01-01",
        end_date="2024-06-01",
        algorithm_version="alphabetical_baseline",
        max_universe=8,
        max_results=5,
        forward_horizons=[5, 20],
        price_panel=panel,
    )
    result = run_scan_evaluation(cfg)
    assert result["summary"]["rebalance_count"] == 2
    assert len(result["snapshots"]) == 2
    assert result["production_impact"] == "none — evidence only"


def test_aggregate_ranking_quality_turnover():
    rows = [
        {"symbol": "A", "ranking_score": 90, "sector": "Tech", "forward_outcomes": {"5": {"forward_return_pct": 2.0, "mae_pct": -1.0, "mfe_pct": 3.0}}},
        {"symbol": "B", "ranking_score": 80, "sector": "Tech", "forward_outcomes": {"5": {"forward_return_pct": 1.0, "mae_pct": -0.5, "mfe_pct": 2.0}}},
        {"symbol": "C", "ranking_score": 70, "sector": "Health", "forward_outcomes": {"5": {"forward_return_pct": 0.5, "mae_pct": -0.2, "mfe_pct": 1.0}}},
        {"symbol": "D", "ranking_score": 60, "sector": "Energy", "forward_outcomes": {"5": {"forward_return_pct": -0.5, "mae_pct": -2.0, "mfe_pct": 0.5}}},
        {"symbol": "E", "ranking_score": 50, "sector": "Energy", "forward_outcomes": {"5": {"forward_return_pct": -1.0, "mae_pct": -3.0, "mfe_pct": 0.2}}},
    ]
    out = aggregate_ranking_quality(rows, horizon=5, prev_top_symbols={"A", "X"})
    assert out["cross_section"]["sufficient"] is True
    assert out["sector_concentration"]["top_sector"] == "Tech"
    assert out["stability"]["turnover"] is not None
