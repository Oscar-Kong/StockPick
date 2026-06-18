"""Tests for canonical portfolio summary endpoint."""
from __future__ import annotations

from unittest.mock import patch

from services.portfolio_summary_service import build_portfolio_summary


def test_build_portfolio_summary_uses_ledger():
    fake_dashboard = type(
        "Dash",
        (),
        {
            "portfolio_value": 10000.0,
            "cash": 1000.0,
            "reserved_cash": 0.0,
            "invested_value": 9000.0,
            "holdings": [{"symbol": "AAPL", "shares": 10, "avg_cost": 150, "bucket": "penny"}],
            "decision": None,
            "data_source": "csv",
            "data_source_label": "Robinhood CSV",
            "is_demo_data": False,
            "portfolio_warnings": [],
            "decision_stale_warning": None,
            "freshness": None,
            "disclaimer": "Research only",
        },
    )()

    with patch("services.portfolio_summary_service.build_daily_dashboard", return_value=fake_dashboard):
        with patch("services.portfolio_summary_service.get_current_portfolio", return_value={"account": {}}):
            with patch("services.portfolio_summary_service.get_latest_portfolio_snapshot", return_value=None):
                with patch("services.portfolio_summary_service.get_latest_decision", return_value=None):
                    with patch("services.portfolio_summary_service._position_rows", return_value=[]):
                        summary = build_portfolio_summary(include_freshness=False)

    assert summary["source"] == "portfolio_ledger"
    assert summary["total_value"] == 10000.0
    assert summary["cash"] == 1000.0
    assert summary["data_source"] == "csv"


def test_build_portfolio_summary_with_freshness_uses_latest_prices_key():
    fake_dashboard = type(
        "Dash",
        (),
        {
            "portfolio_value": 1000.0,
            "cash": 0.0,
            "reserved_cash": 0.0,
            "invested_value": 1000.0,
            "holdings": [],
            "decision": None,
            "data_source": "csv",
            "data_source_label": "CSV",
            "is_demo_data": False,
            "portfolio_warnings": [],
            "decision_stale_warning": None,
            "freshness": None,
            "disclaimer": "Research only",
        },
    )()
    fake_status = type("Status", (), {"is_stale": False, "last_updated_at": "2026-01-01"})()

    with patch("services.portfolio_summary_service.build_daily_dashboard", return_value=fake_dashboard):
        with patch("services.portfolio_summary_service.get_current_portfolio", return_value={"account": {}}):
            with patch("services.portfolio_summary_service.get_latest_portfolio_snapshot", return_value=None):
                with patch("services.portfolio_summary_service.get_latest_decision", return_value=None):
                    with patch("services.portfolio_summary_service._position_rows", return_value=[]):
                        with patch(
                            "services.portfolio_summary_service.assess_freshness",
                            return_value=fake_status,
                        ) as assess:
                            summary = build_portfolio_summary(include_freshness=True)

    assess.assert_called_once_with("latest_prices")
    assert summary["stale"] is False
