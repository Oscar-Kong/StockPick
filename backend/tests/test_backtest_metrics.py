"""Unified backtest metrics — unit and regression tests."""
from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.backtest.metrics import (
    annualized_return_pct,
    annualized_volatility_pct,
    benchmark_alpha_beta,
    calmar_ratio,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
    summarize_portfolio_backtest,
    summarize_trade_backtest,
    turnover_pct,
    win_rate_pct,
)
from ml.backtest_engine import compute_metrics
from services.policy_backtest import PolicyBacktestResult, run_policy_backtest


def test_sharpe_sortino_calmar_max_drawdown():
    rets = pd.Series([0.01, -0.02, 0.015, -0.01, 0.02, 0.005, -0.008])
    assert sharpe_ratio(rets, ddof=1) != 0.0
    assert sortino_ratio(rets) != 0.0
    assert calmar_ratio(12.0, -8.0) == pytest.approx(1.5)

    equity = pd.Series([100.0, 110.0, 105.0, 115.0, 90.0, 95.0])
    dd = max_drawdown(equity)
    assert dd < 0
    assert dd == pytest.approx(((90.0 - 115.0) / 115.0) * 100, rel=1e-3)


def test_annualized_return_and_volatility():
    total_ret = 0.10
    ann = annualized_return_pct(total_ret, periods=252)
    assert ann == pytest.approx(10.0, rel=1e-3)

    daily = pd.Series(np.random.default_rng(1).normal(0.001, 0.01, 100))
    vol = annualized_volatility_pct(daily, ddof=1)
    assert vol > 0


def test_win_rate_profit_factor_turnover():
    trade_rets = [5.0, -2.0, 3.0, -1.0, 4.0]
    assert win_rate_pct(trade_rets) == 60.0
    assert profit_factor(trade_rets) == pytest.approx(12.0 / 3.0, rel=1e-3)
    assert turnover_pct(0.875) == 87.5


def test_benchmark_alpha_beta():
    rng = np.random.default_rng(0)
    bench = pd.Series(rng.normal(0.0005, 0.01, 120))
    port = 1.2 * bench + rng.normal(0, 0.002, 120)
    out = benchmark_alpha_beta(port, bench)
    assert out["sufficient"] is True
    assert out["beta"] == pytest.approx(1.2, abs=0.25)


def test_summarize_trade_backtest_regression_fields():
    trades = [
        {"return_pct": 10.0, "gross_return_pct": 10.5, "days_held": 20},
        {"return_pct": -5.0, "gross_return_pct": -4.5, "days_held": 15},
        {"return_pct": 8.0, "days_held": 20},
    ]
    equity = [10_000.0, 11_000.0, 10_450.0, 11_286.0]
    legacy = compute_metrics(trades, equity, 10_000.0, hold_days=20, benchmark_return_pct=3.5)
    shared = summarize_trade_backtest(trades, equity, 10_000.0, 20, 3.5)

    expected_keys = {
        "total_return_pct",
        "gross_return_pct",
        "annualized_return_pct",
        "win_rate_pct",
        "max_drawdown_pct",
        "sharpe_ratio",
        "trade_count",
        "buy_hold_return_pct",
        "costs_applied",
    }
    assert set(legacy.keys()) == expected_keys
    assert legacy == shared
    assert legacy["trade_count"] == 3
    assert legacy["win_rate_pct"] == pytest.approx(66.7, abs=0.1)
    assert legacy["buy_hold_return_pct"] == 3.5


def test_summarize_trade_backtest_empty():
    out = summarize_trade_backtest([], [10_000.0], 10_000.0, 20, 0.0)
    assert out["trade_count"] == 0
    assert out["sharpe_ratio"] == 0.0
    assert out["win_rate_pct"] == 0.0


def test_summarize_portfolio_backtest_matches_legacy_formulas():
    rng = np.random.default_rng(42)
    n = 200
    dates = pd.bdate_range("2024-01-02", periods=n)
    daily_rets = pd.Series(rng.normal(0.0004, 0.008, n), index=dates)
    equity = (1.0 + daily_rets).cumprod() * 10_000.0

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    port_rets = equity.pct_change().dropna()

    legacy_ann = ((1.0 + total_return) ** (252.0 / n) - 1.0) * 100.0
    peak = equity.cummax()
    legacy_dd = float(((equity - peak) / peak.replace(0, np.nan)).min() * 100)
    legacy_vol = float(port_rets.std(ddof=1) * np.sqrt(252) * 100)
    legacy_sharpe = float((port_rets.mean() / port_rets.std(ddof=1)) * np.sqrt(252))

    metrics = summarize_portfolio_backtest(
        equity,
        turnover_sum=1.25,
        total_return=total_return,
        periods=n,
    )

    assert metrics["annualized_return_pct"] == pytest.approx(round(legacy_ann, 2), abs=0.01)
    assert metrics["max_drawdown_pct"] == pytest.approx(round(legacy_dd, 2), abs=0.01)
    assert metrics["volatility_pct"] == pytest.approx(round(legacy_vol, 2), abs=0.01)
    assert metrics["sharpe_ratio"] == pytest.approx(round(legacy_sharpe, 2), abs=0.01)
    assert metrics["turnover_pct"] == 125.0


def test_policy_backtest_result_fields():
    """Regression: PolicyBacktestResult dataclass fields unchanged."""
    names = {f.name for f in fields(PolicyBacktestResult)}
    assert names == {
        "policy",
        "rebalance",
        "lookback_period",
        "symbols_used",
        "excluded",
        "initial_capital",
        "final_capital",
        "total_return_pct",
        "annualized_return_pct",
        "max_drawdown_pct",
        "volatility_pct",
        "sharpe_ratio",
        "benchmark_return_pct",
        "turnover_pct",
        "rebalance_count",
        "equity_curve",
        "weights_history",
        "notes",
    }


def _synthetic_hist(n: int = 120, start: float = 100.0, drift: float = 0.0005) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2023-06-01", periods=n)
    closes = [start]
    for _ in range(n - 1):
        closes.append(closes[-1] * (1.0 + drift + rng.normal(0, 0.008)))
    return pd.DataFrame(
        {"date": dates, "open": closes, "high": closes, "low": closes, "close": closes, "volume": 1e6}
    )


@patch("services.policy_backtest.PriceService")
def test_run_policy_backtest_response_shape(mock_ps):
    hist_a = _synthetic_hist(120, start=100.0)
    hist_b = _synthetic_hist(120, start=50.0)
    hist_spy = _synthetic_hist(120, start=400.0, drift=0.0003)

    def get_history(symbol, period="1y"):
        sym = symbol.upper()
        if sym == "AAA":
            return hist_a
        if sym == "BBB":
            return hist_b
        return pd.DataFrame()

    mock_ps.return_value.get_history.side_effect = get_history
    mock_ps.return_value.get_spy_history.return_value = hist_spy

    result = run_policy_backtest(["AAA", "BBB"], lookback_period="1y", initial_capital=10_000.0)

    assert isinstance(result, PolicyBacktestResult)
    assert result.symbols_used == ["AAA", "BBB"]
    assert result.initial_capital == 10_000.0
    assert result.final_capital > 0
    assert isinstance(result.total_return_pct, float)
    assert isinstance(result.annualized_return_pct, float)
    assert isinstance(result.max_drawdown_pct, float)
    assert isinstance(result.volatility_pct, float)
    assert isinstance(result.sharpe_ratio, float)
    assert isinstance(result.benchmark_return_pct, float)
    assert isinstance(result.turnover_pct, float)
    assert result.rebalance_count >= 1
    assert len(result.equity_curve) > 0
    assert len(result.weights_history) > 0
    assert result.notes
