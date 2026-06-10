"""Home dashboard API tests."""
from __future__ import annotations

from services.home_dashboard_service import _risk_alerts, build_daily_dashboard
from models.schemas import PortfolioDecisionItem, PortfolioDecisionResponse


def test_risk_alerts_tolerates_legacy_snapshot_fields():
    decision = PortfolioDecisionResponse(
        as_of="2025-01-01",
        cash=100.0,
        total_value=1000.0,
        items=[
            PortfolioDecisionItem(
                symbol="AMC",
                bucket="penny",
                price=1.9,
                shares=20,
                avg_cost=1.95,
                market_value=38.0,
                current_weight=4.0,
                target_weight=3.0,
                buy_pct=0,
                keep_pct=100,
                sell_pct=0,
                decision="keep",
                score=50,
                risk_index=50,
                suggested_dollar_action=0,
                risk_flags=["overweight"],
                overweight_penalty=None,
                risk_score=None,
                price_available=True,
            )
        ],
    )
    alerts = _risk_alerts(decision, {"holdings": [{"symbol": "AMC"}], "is_demo_data": False})
    assert any("AMC" in a for a in alerts)


def test_build_daily_dashboard_does_not_crash():
    result = build_daily_dashboard()
    assert result.portfolio_value >= 0
    assert result.disclaimer
