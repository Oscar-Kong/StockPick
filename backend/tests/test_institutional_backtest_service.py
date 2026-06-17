"""Tests for portfolio policy / institutional backtest response wiring."""
from __future__ import annotations

from engines.backtest.institutional import InstitutionalBacktestResult
from services.institutional_backtest_service import _to_response
from services.policy_backtest import PolicyBacktestResult


def test_to_response_institutional_does_not_duplicate_institutional_kwarg():
    result = InstitutionalBacktestResult(
        policy="equal_weight",
        rebalance="monthly",
        lookback_period="1y",
        symbols_used=["AAPL", "MSFT"],
        excluded=[],
        initial_capital=100_000.0,
        final_capital=110_000.0,
        total_return_pct=10.0,
        annualized_return_pct=8.0,
        max_drawdown_pct=-5.0,
        volatility_pct=12.0,
        sharpe_ratio=1.1,
        benchmark_return_pct=7.0,
        turnover_pct=20.0,
        rebalance_count=3,
        equity_curve=[],
        weights_history=[],
        notes=[],
        engine="institutional",
        sortino_ratio=1.2,
        calmar_ratio=1.0,
        beta=1.05,
        alpha_vs_spy_pct=2.0,
        total_cost_pct=0.5,
        total_cost_usd=500.0,
        run_id="run_test",
        cost_events=[],
    )

    resp = _to_response(result, symbols_requested=["AAPL", "MSFT"], institutional=True)

    assert resp.institutional is True
    assert resp.run_id == "run_test"
    assert resp.sharpe_ratio == 1.1


def test_to_response_simple_policy():
    result = PolicyBacktestResult(
        policy="equal_weight",
        rebalance="monthly",
        lookback_period="1y",
        symbols_used=["AAPL", "MSFT"],
        excluded=[],
        initial_capital=100_000.0,
        final_capital=105_000.0,
        total_return_pct=5.0,
        annualized_return_pct=4.0,
        max_drawdown_pct=-3.0,
        volatility_pct=10.0,
        sharpe_ratio=0.9,
        benchmark_return_pct=6.0,
        turnover_pct=15.0,
        rebalance_count=2,
        equity_curve=[],
        benchmark_equity_curve=[],
        start_date=None,
        end_date=None,
        weights_history=[],
        notes=[],
    )

    resp = _to_response(result, symbols_requested=["AAPL", "MSFT"], institutional=False)

    assert resp.institutional is False
    assert resp.engine == "policy_sim"
