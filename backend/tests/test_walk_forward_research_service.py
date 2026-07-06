"""Tests for walk_forward_research_service."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
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

from services.walk_forward_research_service import (
    WalkForwardConfig,
    cross_section_metrics,
    rebalance_dates,
    run_walk_forward_research,
    turnover_rate,
    universe_for_date,
    _truncate_history,
)


def _ohlc(n: int, start: str = "2023-01-03", step_pct: float = 0.001) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=n)
    closes = [100.0]
    for _ in range(n - 1):
        closes.append(closes[-1] * (1.0 + step_pct))
    return pd.DataFrame(
        {
            "date": [d.date() for d in dates],
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1_000_000] * n,
        }
    )


def test_cross_section_metrics_insufficient():
    out = cross_section_metrics([1.0, 2.0], [0.01, 0.02])
    assert out["sufficient"] is False
    assert out["reason"] == "insufficient_cross_section"


def test_cross_section_metrics_positive_ic():
    scores = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    fwd = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    out = cross_section_metrics(scores, fwd)
    assert out["sufficient"] is True
    assert out["pearson_ic"] == pytest.approx(1.0, abs=1e-6)
    assert out["rank_ic"] == pytest.approx(1.0, abs=1e-6)
    assert out["hit_rate"] >= 0.5
    assert out["top_quintile_avg_return"] is not None
    assert out["top_minus_bottom_spread"] is not None
    assert out["top_minus_bottom_spread"] > 0


def test_turnover_rate():
    assert turnover_rate({"A", "B", "C"}, {"A", "B", "D"}) == pytest.approx(0.3333, abs=1e-3)
    assert turnover_rate(set(), {"A"}) == 1.0
    assert turnover_rate({"A"}, set()) == 1.0
    assert turnover_rate(set(), set()) == 0.0


def test_truncate_history_no_lookahead():
    hist = _ohlc(10, start="2024-01-02")
    as_of = date(2024, 1, 10)
    trimmed = _truncate_history(hist, as_of)
    assert not trimmed.empty
    assert trimmed["date"].max() <= as_of
    assert len(trimmed) < len(hist)


def test_rebalance_dates_invalid_range():
    with pytest.raises(ValueError, match="start_date"):
        rebalance_dates("2024-06-01", "2024-01-01", "monthly")


@patch("services.walk_forward_research_service.active_symbols_on_date")
@patch("services.walk_forward_research_service.get_universe")
def test_universe_for_date_pit(mock_universe, mock_pit):
    mock_universe.return_value = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]
    mock_pit.return_value = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]
    symbols, source = universe_for_date("penny", date(2024, 6, 1), max_symbols=10)
    assert source == "pit"
    assert symbols == ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]


@patch("services.walk_forward_research_service.active_symbols_on_date")
@patch("services.walk_forward_research_service.get_universe")
def test_universe_for_date_fallback(mock_universe, mock_pit):
    mock_universe.return_value = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]
    mock_pit.return_value = []
    symbols, source = universe_for_date("penny", date(2024, 6, 1), max_symbols=3)
    assert source == "fallback"
    assert len(symbols) == 3


def _mock_scoring(score: float):
    factor = SimpleNamespace(
        factor_id="momentum",
        display_name="Momentum",
        norm_score=score,
        weight=1.0,
        contribution=score,
    )
    return SimpleNamespace(
        final_score=score,
        raw_score=score,
        regime_mult=1.0,
        sector_tilt=0.0,
        dq_multiplier=1.0,
        factors=[factor],
    )


def _mock_risk():
    return SimpleNamespace(risk_score=25.0, deduction_pts=0.0, breakdown={"vol": 25.0})


@patch("services.walk_forward_research_service.persist_walk_forward_run")
@patch("services.walk_forward_research_service._persist_research_snapshot")
@patch("services.walk_forward_research_service.RiskEngine.assess", side_effect=lambda *a, **k: _mock_risk())
@patch("services.walk_forward_research_service.ScoringEngine.score")
@patch("services.walk_forward_research_service.universe_for_date")
@patch("services.walk_forward_research_service.rebalance_dates")
def test_run_walk_forward_research_synthetic(
    mock_dates,
    mock_universe,
    mock_score,
    mock_risk,
    mock_snap,
    mock_persist_run,
):
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ"]
    as_of = date(2024, 6, 3)
    mock_dates.return_value = [as_of]
    mock_universe.return_value = (symbols, "pit")

    score_map = {sym: float(i + 1) * 10 for i, sym in enumerate(symbols)}

    def score_side_effect(ctx, sleeve, **kwargs):
        return _mock_scoring(score_map[ctx.symbol])

    mock_score.side_effect = score_side_effect

    panel = {sym: _ohlc(120, step_pct=0.002 * (i + 1)) for i, sym in enumerate(symbols)}
    for sym, df in panel.items():
        df.attrs["symbol"] = sym

    with patch(
        "services.walk_forward_research_service._forward_return_pct",
        side_effect=lambda hist, start, horizon: float(symbols.index(hist.attrs["symbol"]) + 1),
    ):
        cfg = WalkForwardConfig(
            sleeve="penny",
            start_date="2024-01-01",
            end_date="2024-06-30",
            rebalance_frequency="monthly",
            forward_horizons=[5, 10],
            max_symbols=10,
            persist_snapshots=False,
        )
        summary = run_walk_forward_research(cfg, price_panel=panel, spy_hist=_ohlc(120))

    assert summary["status"] == "completed"
    assert summary["weights_updated"] is False
    assert summary["periods_scored"] == 1
    assert summary["rebalance_periods"] == 1
    h5 = summary["periods"][0]["horizons"]["5"]
    assert h5["sufficient"] is True
    assert h5["pearson_ic"] == pytest.approx(1.0, abs=1e-6)
    mock_persist_run.assert_called_once()


@patch("services.walk_forward_research_service.persist_walk_forward_run")
@patch("services.walk_forward_research_service.rebalance_dates")
def test_run_walk_forward_tail_insufficient_forward(mock_dates, mock_persist_run):
    """Last rebalance with no forward data should still complete with insufficient metrics."""
    as_of = date(2024, 12, 31)
    mock_dates.return_value = [as_of]
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ"]
    panel = {sym: _ohlc(80) for sym in symbols}

    with (
        patch("services.walk_forward_research_service.universe_for_date", return_value=(symbols, "fallback")),
        patch("services.walk_forward_research_service.ScoringEngine.score", side_effect=lambda ctx, *a, **k: _mock_scoring(50.0)),
        patch("services.walk_forward_research_service.RiskEngine.assess", side_effect=lambda *a, **k: _mock_risk()),
        patch("services.walk_forward_research_service._forward_return_pct", return_value=None),
    ):
        cfg = WalkForwardConfig(
            sleeve="penny",
            start_date="2024-12-01",
            end_date="2024-12-31",
            forward_horizons=[20],
            persist_snapshots=False,
        )
        summary = run_walk_forward_research(cfg, price_panel=panel)

    assert summary["status"] == "completed"
    metrics = summary["periods"][0]["horizons"]["20"]
    assert metrics["sufficient"] is False
