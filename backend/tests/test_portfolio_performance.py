"""Tests for portfolio performance metrics and curves."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from integrations.robinhood.mcp_pnl import RealizedPnlSummary
from services.portfolio_performance_service import (
    _closed_realized_ytd,
    _curve_period_change,
    _filter_curve_ytd,
    _slice_curve,
    _ytd_floor,
    build_portfolio_performance,
)


def test_curve_period_change():
    curve = [{"date": "2026-01-01", "value": 100}, {"date": "2026-01-02", "value": 110}]
    assert _curve_period_change(curve) == 10.0


def test_filter_curve_ytd_drops_prior_year():
    floor = _ytd_floor()
    curve = [
        {"date": "2025-12-31", "value": 90},
        {"date": f"{floor[:4]}-01-02", "value": 100},
        {"date": f"{floor[:4]}-01-03", "value": 110},
    ]
    filtered = _filter_curve_ytd(curve)
    assert all(p["date"] >= floor for p in filtered)
    assert filtered[0]["value"] == 100


def test_closed_realized_ytd_excludes_prior_year():
    floor = _ytd_floor()
    year = floor[:4]
    closed = [
        {"symbol": "NEW", "realized_pl": 10.0, "last_activity": f"{year}-03-01"},
        {"symbol": "ROBIN", "realized_pl": 7.5, "last_activity": f"03/15/{year}"},
        {"symbol": "OLD", "realized_pl": 500.0, "last_activity": "11/01/2025"},
        {"symbol": "NODATE", "realized_pl": 99.0, "last_activity": ""},
    ]
    assert _closed_realized_ytd(closed) == 17.5


def test_slice_curve_limits_points():
    curve = [{"date": f"2026-06-{i:02d}", "value": float(i)} for i in range(1, 31)]
    sliced = _slice_curve(curve, 7)
    assert len(sliced) == 7
    assert sliced[0]["date"] == "2026-06-24"


def test_build_portfolio_performance_metrics():
    summary = {
        "total_value": 1000,
        "invested_value": 800,
        "cash": 200,
        "reserved_cash": 0,
        "as_of": "2026-07-03T00:00:00Z",
        "positions": [
            {
                "symbol": "AMC",
                "shares": 10,
                "avg_cost": 5,
                "price": 6,
                "market_value": 60,
                "daily_change_pct": 5.0,
            }
        ],
    }
    closed = [{"symbol": "OLD", "realized_pl": 25.5, "last_activity": "06/15/2026"}]

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2025-11-01", "2026-06-01", "2026-06-02", "2026-07-01", "2026-07-02"]
            ),
            "open": [4.5, 5, 5.1, 5.8, 6],
            "high": [4.7, 5.2, 5.2, 6, 6.1],
            "low": [4.4, 4.9, 5, 5.7, 5.9],
            "close": [4.6, 5, 5.1, 5.9, 6],
            "volume": [1000, 1000, 1000, 1000, 1000],
        }
    )

    with patch("services.portfolio_performance_service.build_portfolio_summary", return_value=summary):
        with patch("services.portfolio_performance_service.Cache") as cache_cls:
            cache_cls.return_value.get.return_value = None
            with patch("services.portfolio_performance_service.load_all_ledger_rows", return_value=[]):
                with patch(
                    "services.portfolio_performance_service.RobinhoodMcpClient"
                ) as mcp_cls:
                    mcp_cls.return_value.fetch_ytd_realized_pnl_sync.return_value = RealizedPnlSummary(
                        total=25.5,
                        equity=20.0,
                        events=5.5,
                        trade_count=3,
                        source="robinhood_mcp",
                    )
                    with patch("services.portfolio_performance_service.PriceService") as ps_cls:
                        ps_cls.return_value.get_history.return_value = df
                        out = build_portfolio_performance(closed_positions=closed)

    assert out["total_value"] == 1000
    assert out["realized_pl"] == 25.5
    assert out["realized_pl_equity"] == 20.0
    assert out["realized_pl_events"] == 5.5
    assert out["realized_pl_source"] == "robinhood_mcp"
    assert out["unrealized_pl"] == 10.0
    assert out["today_pl"] > 0
    assert "1m" in out["curves"]
    assert len(out["curves"]["1m"]) >= 2
    assert "cost basis" in out["disclaimer"]
