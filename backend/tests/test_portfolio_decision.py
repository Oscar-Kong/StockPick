"""Tests for portfolio daily decision service."""
from __future__ import annotations

from unittest.mock import patch

from models.schemas import Bucket, PortfolioDecisionRequest, PortfolioHolding
from services.portfolio_decision_service import run_portfolio_daily_decision


def test_daily_decision_returns_items():
    holding = PortfolioHolding(symbol="AAPL", shares=10, avg_cost=150, bucket=Bucket.penny)
    body = PortfolioDecisionRequest(cash=1000, holdings=[holding])

    fake_ctx = {
        "alpha": 72.0,
        "risk_index": 45.0,
        "target_weight": 0.02,
        "dq": 80.0,
        "risk_flags": [],
        "momentum": 50.0,
        "liquidity": 60.0,
    }

    with patch("services.portfolio_decision_service._last_price", return_value=180.0):
        with patch("services.portfolio_decision_service._score_context", return_value=fake_ctx):
            res = run_portfolio_daily_decision(body)

    assert len(res.items) == 1
    item = res.items[0]
    assert item.symbol == "AAPL"
    assert item.bucket == "penny"
    assert item.decision in ("buy", "keep", "trim", "sell", "watch")
    assert abs(item.buy_pct + item.keep_pct + item.sell_pct - 100) < 0.01
    assert any("not financial advice" in n.lower() for n in res.notes)
