"""Generic backtest engine with multi-horizon and out-of-sample validation."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

HORIZON_MAP = {
    "1y": 252,
    "3y": 756,
    "5y": 1260,
}

OOS_SPLIT = 0.7  # 70% in-sample, 30% out-of-sample


def slice_by_horizon(df: pd.DataFrame, horizon: str) -> pd.DataFrame:
    bars = HORIZON_MAP.get(horizon, 504)
    if len(df) <= bars:
        return df.copy()
    return df.iloc[-bars:].copy().reset_index(drop=True)


def split_in_out_sample(df: pd.DataFrame, split: float = OOS_SPLIT) -> tuple[pd.DataFrame, pd.DataFrame]:
    idx = int(len(df) * split)
    if idx < 60:
        return df.copy(), pd.DataFrame()
    return df.iloc[:idx].copy().reset_index(drop=True), df.iloc[idx:].copy().reset_index(drop=True)


def compute_metrics(
    trades: list[dict],
    equity_curve: list[float],
    initial_capital: float,
    hold_days: int,
    benchmark_return_pct: float = 0.0,
) -> dict[str, Any]:
    if not trades:
        return {
            "total_return_pct": 0.0,
            "gross_return_pct": 0.0,
            "annualized_return_pct": 0.0,
            "win_rate_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "trade_count": 0,
            "buy_hold_return_pct": benchmark_return_pct,
            "costs_applied": any("gross_return_pct" in t for t in trades),
        }

    capital = equity_curve[-1] if equity_curve else initial_capital
    total_return = (capital / initial_capital - 1) * 100
    gross_capital = initial_capital
    for t in trades:
        gross_pct = t.get("gross_return_pct", t.get("return_pct", 0))
        gross_capital *= 1 + float(gross_pct) / 100
    gross_return = (gross_capital / initial_capital - 1) * 100
    returns = np.array([t["return_pct"] / 100 for t in trades])
    wins = (returns > 0).sum()

    eq = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    drawdown = (eq - peak) / peak
    max_dd = float(drawdown.min() * 100) if len(drawdown) else 0.0

    sharpe = 0.0
    if len(returns) > 1 and returns.std() > 0:
        sharpe = float((returns.mean() / returns.std()) * np.sqrt(252 / max(hold_days, 1)))

    # Annualized return approximation
    total_days = sum(max(1, t.get("days_held", hold_days)) for t in trades)
    years = max(total_days / 252, 0.01)
    ann_return = ((capital / initial_capital) ** (1 / years) - 1) * 100

    return {
        "total_return_pct": round(total_return, 2),
        "gross_return_pct": round(gross_return, 2),
        "annualized_return_pct": round(ann_return, 2),
        "win_rate_pct": round(wins / len(trades) * 100, 1),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 2),
        "trade_count": len(trades),
        "buy_hold_return_pct": round(benchmark_return_pct, 2),
        "costs_applied": any("gross_return_pct" in t for t in trades),
    }


def run_simulation(
    stock_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    *,
    entry_fn: Callable,
    hold_days: int = 20,
    stop_pct: float = 0.07,
    target_pct: float | None = 0.10,
    initial_capital: float = 10_000.0,
    warmup: int = 55,
    sleeve: str | None = "medium",
    apply_costs: bool | None = None,
) -> tuple[list[dict], list[float], float]:
    """Run a generic long-only simulation with stop/target/time exits."""
    from config import LEGACY_BACKTEST_COSTS_ENABLED
    from engines.backtest.cost_model import trade_cost_usd

    use_costs = LEGACY_BACKTEST_COSTS_ENABLED if apply_costs is None else apply_costs
    if len(stock_df) < warmup + 5:
        return [], [initial_capital], 0.0

    df = stock_df.copy().reset_index(drop=True)
    capital = initial_capital
    equity_curve = [capital]
    trades: list[dict] = []
    position: dict | None = None

    for i in range(warmup, len(df) - 1):
        window = df.iloc[: i + 1]
        spy_window = spy_df.iloc[: min(i + 1, len(spy_df))]

        if position is None:
            if entry_fn(window, spy_window, i):
                entry = float(df.iloc[i]["close"])
                position = {
                    "entry_idx": i,
                    "entry_price": entry,
                    "stop": entry * (1 - stop_pct),
                    "target": entry * (1 + target_pct) if target_pct else None,
                }
        else:
            days_held = i - position["entry_idx"]
            row = df.iloc[i]
            low = float(row["low"])
            high = float(row["high"])
            close = float(row["close"])
            exit_price = None
            reason = None

            if low <= position["stop"]:
                exit_price = position["stop"]
                reason = "stop"
            elif position["target"] and high >= position["target"]:
                exit_price = position["target"]
                reason = "target"
            elif days_held >= hold_days:
                exit_price = close
                reason = "time"

            if exit_price is not None:
                ret = (exit_price - position["entry_price"]) / position["entry_price"]
                gross_ret = ret
                if use_costs:
                    notional = capital
                    cost = trade_cost_usd(notional, sleeve=sleeve)
                    ret = ret - cost / max(notional, 1.0)
                capital *= 1 + ret
                trades.append(
                    {
                        "entry_date": str(df.iloc[position["entry_idx"]]["date"]),
                        "exit_date": str(row["date"]),
                        "return_pct": round(ret * 100, 2),
                        "gross_return_pct": round(gross_ret * 100, 2),
                        "reason": reason,
                        "days_held": days_held,
                    }
                )
                position = None

        equity_curve.append(capital)

    bh_ret = 0.0
    if len(df) > warmup:
        bh_ret = (float(df.iloc[-1]["close"]) / float(df.iloc[warmup]["close"]) - 1) * 100

    return trades, equity_curve, bh_ret


def run_backtest_with_oos(
    stock_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    *,
    entry_fn: Callable,
    horizon: str = "3y",
    hold_days: int = 20,
    stop_pct: float = 0.07,
    target_pct: float | None = 0.10,
    initial_capital: float = 10_000.0,
    strategy_version: str = "unknown",
) -> dict[str, Any]:
    """Run full-period, in-sample, and out-of-sample backtests."""
    df = slice_by_horizon(stock_df, horizon)
    spy = slice_by_horizon(spy_df, horizon)

    if len(df) < 80:
        return _empty(f"Insufficient history for {horizon} horizon")

    in_sample, out_sample = split_in_out_sample(df)
    spy_in, spy_out = split_in_out_sample(spy)

    full_trades, full_eq, full_bh = run_simulation(
        df, spy, entry_fn=entry_fn, hold_days=hold_days, stop_pct=stop_pct, target_pct=target_pct,
        initial_capital=initial_capital,
    )
    full_metrics = compute_metrics(full_trades, full_eq, initial_capital, hold_days, full_bh)

    is_trades, is_eq, is_bh = run_simulation(
        in_sample, spy_in, entry_fn=entry_fn, hold_days=hold_days, stop_pct=stop_pct,
        target_pct=target_pct, initial_capital=initial_capital,
    )
    is_metrics = compute_metrics(is_trades, is_eq, initial_capital, hold_days, is_bh)

    oos_metrics: dict[str, Any] = {}
    oos_trades: list[dict] = []
    if not out_sample.empty and len(out_sample) >= 60:
        oos_trades, oos_eq, oos_bh = run_simulation(
            out_sample, spy_out, entry_fn=entry_fn, hold_days=hold_days, stop_pct=stop_pct,
            target_pct=target_pct, initial_capital=initial_capital,
        )
        oos_metrics = compute_metrics(oos_trades, oos_eq, initial_capital, hold_days, oos_bh)

    # Strategy pass/fail: OOS Sharpe > 0 and win rate >= 40%
    passed = True
    fail_reasons: list[str] = []
    if oos_metrics:
        if oos_metrics.get("sharpe_ratio", 0) <= 0:
            passed = False
            fail_reasons.append("OOS Sharpe <= 0")
        if oos_metrics.get("win_rate_pct", 0) < 40:
            passed = False
            fail_reasons.append("OOS win rate < 40%")
    elif not full_trades:
        passed = False
        fail_reasons.append("No trades triggered")

    return {
        "horizon": horizon,
        "strategy_version": strategy_version,
        "backtest_engine": "default",
        "initial_capital": initial_capital,
        "final_capital": round(full_eq[-1], 2) if full_eq else initial_capital,
        **full_metrics,
        "in_sample": is_metrics,
        "out_of_sample": oos_metrics or None,
        "validation_passed": passed,
        "validation_notes": fail_reasons,
        "trades": full_trades[-10:],
        "message": "Quantitative backtest — not investment advice",
    }


def run_multi_horizon_backtest(
    stock_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    *,
    entry_fn: Callable,
    horizons: list[str] | None = None,
    hold_days: int = 20,
    stop_pct: float = 0.07,
    target_pct: float | None = 0.10,
    strategy_version: str = "unknown",
) -> dict[str, Any]:
    horizons = horizons or ["1y", "3y", "5y"]
    results = {}
    for h in horizons:
        sliced = slice_by_horizon(stock_df, h)
        if len(sliced) < 80:
            results[h] = _empty(f"Insufficient data for {h}")
            continue
        spy_sliced = slice_by_horizon(spy_df, h)
        results[h] = run_backtest_with_oos(
            sliced,
            spy_sliced,
            entry_fn=entry_fn,
            horizon=h,
            hold_days=hold_days,
            stop_pct=stop_pct,
            target_pct=target_pct,
            strategy_version=strategy_version,
        )

    # Overall pass if majority of horizons pass validation
    passed_count = sum(1 for r in results.values() if r.get("validation_passed"))
    return {
        "horizons": results,
        "overall_passed": passed_count >= len(horizons) // 2 + 1 if results else False,
        "strategy_version": strategy_version,
        "message": "Multi-horizon backtest — not investment advice",
    }


def _empty(msg: str) -> dict[str, Any]:
    return {
        "total_return_pct": 0,
        "annualized_return_pct": 0,
        "win_rate_pct": 0,
        "max_drawdown_pct": 0,
        "sharpe_ratio": 0,
        "trade_count": 0,
        "buy_hold_return_pct": 0,
        "validation_passed": False,
        "validation_notes": [msg],
        "trades": [],
        "backtest_engine": "default",
        "message": msg,
    }
