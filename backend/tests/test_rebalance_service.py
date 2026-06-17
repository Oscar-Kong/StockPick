"""Tests for rebalance trade preview."""
from __future__ import annotations

import pytest

from services.rebalance_service import compute_rebalance_preview


def _mock_prices(monkeypatch, prices: dict[str, float]):
    import services.rebalance_service as rs

    class FakePS:
        def get_history(self, symbol, period="5d"):
            import pandas as pd

            if symbol not in prices:
                return pd.DataFrame()
            return pd.DataFrame({"date": ["2026-01-01"], "close": [prices[symbol]]})

    monkeypatch.setattr(rs, "PriceService", FakePS)


class TestRebalancePreview:
    def test_buy_sell_hold_actions(self, monkeypatch):
        _mock_prices(monkeypatch, {"AAPL": 100.0, "MSFT": 50.0})
        result = compute_rebalance_preview(
            holdings=[
                {"symbol": "AAPL", "shares": 10},
                {"symbol": "MSFT", "shares": 10},
            ],
            target_weights={"AAPL": 0.60, "MSFT": 0.35},
            cash=0,
            cash_reserve=0.05,
        )
        by_sym = {t["symbol"]: t for t in result["trades"]}
        assert by_sym["AAPL"]["action"] in ("buy", "sell", "hold")
        assert result["total_value"] == pytest.approx(1500.0)

    def test_fractional_vs_whole_shares(self, monkeypatch):
        _mock_prices(monkeypatch, {"AAPL": 100.0})
        frac = compute_rebalance_preview(
            holdings=[{"symbol": "AAPL", "shares": 5}],
            target_weights={"AAPL": 0.95},
            cash=500,
            cash_reserve=0.05,
            fractional_shares=True,
        )
        whole = compute_rebalance_preview(
            holdings=[{"symbol": "AAPL", "shares": 5}],
            target_weights={"AAPL": 0.95},
            cash=500,
            cash_reserve=0.05,
            fractional_shares=False,
        )
        assert isinstance(frac["trades"][0]["share_trade"], float)
        assert whole["trades"][0]["share_trade"] == int(whole["trades"][0]["share_trade"])

    def test_min_trade_threshold_holds_small_trades(self, monkeypatch):
        _mock_prices(monkeypatch, {"AAPL": 100.0})
        result = compute_rebalance_preview(
            holdings=[{"symbol": "AAPL", "shares": 10}],
            target_weights={"AAPL": 0.94},
            cash=50,
            cash_reserve=0.05,
            min_trade_amount=500,
        )
        assert result["trades"][0]["action"] == "hold"

    def test_missing_price_raises(self, monkeypatch):
        _mock_prices(monkeypatch, {})
        with pytest.raises(ValueError, match="Missing price history"):
            compute_rebalance_preview(
                holdings=[{"symbol": "AAPL", "shares": 1}],
                target_weights={"AAPL": 0.95},
                cash=0,
            )

    def test_negative_cash_rejected(self, monkeypatch):
        _mock_prices(monkeypatch, {"AAPL": 100.0})
        with pytest.raises(ValueError, match="Cash cannot be negative"):
            compute_rebalance_preview(
                holdings=[{"symbol": "AAPL", "shares": 1}],
                target_weights={"AAPL": 0.95},
                cash=-1,
            )

    def test_max_turnover_violation(self, monkeypatch):
        _mock_prices(monkeypatch, {"AAPL": 100.0, "MSFT": 50.0})
        result = compute_rebalance_preview(
            holdings=[
                {"symbol": "AAPL", "shares": 10},
                {"symbol": "MSFT", "shares": 0},
            ],
            target_weights={"AAPL": 0.20, "MSFT": 0.75},
            cash=0,
            cash_reserve=0.05,
            max_turnover=0.01,
        )
        assert len(result["constraint_violations"]) >= 1
