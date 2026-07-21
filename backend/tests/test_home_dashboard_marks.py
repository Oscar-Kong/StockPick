"""Home dashboard mark alignment — current shares × mark, not stale decision MV."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from models.schemas import PortfolioDecisionItem, PortfolioDecisionResponse
from services.home_dashboard_service import build_daily_dashboard


def _decision_item(*, shares: float, price: float, market_value: float) -> PortfolioDecisionItem:
    return PortfolioDecisionItem(
        symbol="AMC",
        bucket="penny",
        price=price,
        shares=shares,
        avg_cost=1.5,
        market_value=market_value,
        current_weight=50.0,
        target_weight=5.0,
        buy_pct=0,
        keep_pct=100,
        sell_pct=0,
        decision="keep",
        score=50,
        risk_index=50,
        suggested_dollar_action=0,
        risk_flags=[],
        price_available=True,
    )


def test_invested_value_uses_current_shares_times_decision_price():
    """After RH sync, holdings shares can change while decision MV stays frozen."""
    decision = PortfolioDecisionResponse(
        as_of="2025-01-01",
        cash=100.0,
        total_value=300.0,
        invested_value=100.0,
        items=[_decision_item(shares=50, price=2.0, market_value=100.0)],
    )
    with patch("services.home_dashboard_service.get_current_portfolio") as gp:
        gp.return_value = {
            "account": {"source": "robinhood_mcp"},
            "cash": 100.0,
            "reserved_cash": 0.0,
            "holdings": [{"symbol": "AMC", "shares": 100.0, "avg_cost": 1.5}],
            "closed_positions": [],
            "data_source": "robinhood_mcp",
            "is_demo_data": False,
        }
        with patch("services.home_dashboard_service.get_latest_decision") as gd:
            gd.return_value = {"created_at": "2025-01-01", "payload": decision.model_dump()}
            with patch("services.home_dashboard_service.get_latest_portfolio_snapshot", return_value=None):
                with patch("services.home_dashboard_service.build_daily_trading_plan", return_value=None):
                    with patch(
                        "services.portfolio_snapshot_service.robinhood_mcp_status",
                        return_value={"enabled": True, "authenticated": True},
                    ):
                        result = build_daily_dashboard(include_freshness=False)

    assert result.invested_value == 200.0  # 100 shares × $2 mark
    assert result.portfolio_value == 300.0  # cash + invested


def test_cash_only_dashboard_skips_decision_stale_warning():
    with patch("services.home_dashboard_service.get_current_portfolio") as gp:
        gp.return_value = {
            "account": {"source": "robinhood_mcp"},
            "cash": 2105.82,
            "reserved_cash": 0.0,
            "holdings": [],
            "closed_positions": [],
            "data_source": "robinhood_mcp",
            "is_demo_data": False,
        }
        with patch("services.home_dashboard_service.get_latest_decision", return_value=None):
            with patch("services.home_dashboard_service.get_latest_portfolio_snapshot", return_value=None):
                with patch("services.home_dashboard_service.build_daily_trading_plan", return_value=None):
                    with patch(
                        "services.portfolio_snapshot_service.robinhood_mcp_status",
                        return_value={"enabled": True, "authenticated": True},
                    ):
                        with patch(
                            "services.home_dashboard_service.assess_freshness",
                        ) as assess:
                            assess.return_value = MagicMock(is_stale=True, is_missing=False)
                            result = build_daily_dashboard(include_freshness=True)

    assert result.decision_stale_warning is None
    assert result.active_holdings_count == 0
    assert result.cash == 2105.82
    assert result.risk_alerts == []


def test_dashboard_drops_orphan_decision_symbols():
    """Stale journal healthcheck symbols must not appear when holdings are empty."""
    decision = PortfolioDecisionResponse(
        as_of="2025-01-01",
        cash=2105.82,
        total_value=2106.82,
        invested_value=1.0,
        items=[_decision_item(shares=1, price=1.0, market_value=1.0)],
    )
    # Override symbol on the fixture item
    decision.items[0].symbol = "ZZZZ"
    with patch("services.home_dashboard_service.get_current_portfolio") as gp:
        gp.return_value = {
            "account": {"source": "robinhood_mcp"},
            "cash": 2105.82,
            "reserved_cash": 0.0,
            "holdings": [],
            "closed_positions": [],
            "data_source": "robinhood_mcp",
            "is_demo_data": False,
        }
        with patch("services.home_dashboard_service.get_latest_decision") as gd:
            gd.return_value = {"created_at": "2025-01-01", "payload": decision.model_dump()}
            with patch("services.home_dashboard_service.get_latest_portfolio_snapshot", return_value=None):
                with patch("services.home_dashboard_service.build_daily_trading_plan", return_value=None):
                    with patch(
                        "services.portfolio_snapshot_service.robinhood_mcp_status",
                        return_value={"enabled": True, "authenticated": True},
                    ):
                        result = build_daily_dashboard(include_freshness=False)

    assert result.decision is None or result.decision.items == []
    assert result.invested_value == 0.0
    assert not any("ZZZZ" in a for a in (result.risk_alerts or []))
