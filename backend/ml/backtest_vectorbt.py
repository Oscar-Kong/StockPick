"""Optional vectorbt backtest engine adapter."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

HORIZON_MAP = {
    "1y": 252,
    "3y": 756,
    "5y": 1260,
}
OOS_SPLIT = 0.7


def vectorbt_available() -> bool:
    try:
        import vectorbt as _  # noqa: F401

        return True
    except Exception:
        return False


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
        return default if np.isnan(f) or np.isinf(f) else f
    except Exception:
        return default


def _build_entry_exit_signals(
    stock_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    entry_fn: Callable,
    hold_days: int,
    warmup: int = 55,
) -> tuple[pd.Series, pd.Series]:
    entries = pd.Series(False, index=stock_df.index)
    exits = pd.Series(False, index=stock_df.index)

    in_position = False
    entry_idx = -1

    for i in range(warmup, len(stock_df)):
        window = stock_df.iloc[: i + 1]
        spy_window = spy_df.iloc[: min(i + 1, len(spy_df))]

        if not in_position:
            if entry_fn(window, spy_window, i):
                entries.iloc[i] = True
                in_position = True
                entry_idx = i
        elif i - entry_idx >= hold_days:
            exits.iloc[i] = True
            in_position = False

    return entries, exits


def _run_single_window(
    stock_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    *,
    entry_fn: Callable,
    hold_days: int,
    stop_pct: float,
    target_pct: float | None,
    initial_capital: float,
    warmup: int = 55,
) -> dict[str, Any]:
    if len(stock_df) < warmup + 5:
        return _empty("Insufficient bars for vectorbt simulation")

    try:
        import vectorbt as vbt
    except Exception:
        return _empty("vectorbt not installed")

    close = stock_df["close"].astype(float).reset_index(drop=True)
    entries, exits = _build_entry_exit_signals(stock_df, spy_df, entry_fn, hold_days, warmup=warmup)
    if not entries.any():
        return _empty("No trades triggered")

    kwargs: dict[str, Any] = {
        "close": close,
        "entries": entries.reset_index(drop=True),
        "exits": exits.reset_index(drop=True),
        "init_cash": initial_capital,
        "fees": 0.0,
        "freq": "1D",
    }
    if stop_pct > 0:
        kwargs["sl_stop"] = stop_pct
    if target_pct:
        kwargs["tp_stop"] = target_pct

    portfolio = vbt.Portfolio.from_signals(**kwargs)
    total_return_pct = _safe_float(portfolio.total_return() * 100)
    annualized_return_pct = _safe_float(getattr(portfolio, "annualized_return", lambda: np.nan)() * 100)
    max_drawdown_pct = _safe_float(portfolio.max_drawdown() * 100)
    sharpe_ratio = _safe_float(portfolio.sharpe_ratio())
    trade_count = int(_safe_float(portfolio.trades.count()))
    win_rate_pct = _safe_float(portfolio.trades.win_rate() * 100)
    final_capital = initial_capital * (1 + total_return_pct / 100)

    buy_hold_pct = 0.0
    if len(close) > warmup and close.iloc[warmup] > 0:
        buy_hold_pct = ((close.iloc[-1] / close.iloc[warmup]) - 1) * 100

    return {
        "initial_capital": initial_capital,
        "final_capital": round(final_capital, 2),
        "total_return_pct": round(total_return_pct, 2),
        "annualized_return_pct": round(annualized_return_pct, 2),
        "buy_hold_return_pct": round(float(buy_hold_pct), 2),
        "win_rate_pct": round(win_rate_pct, 1),
        "trade_count": trade_count,
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "trades": [],
    }


def run_backtest_with_oos_vectorbt(
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
    if not vectorbt_available():
        return _empty("vectorbt not installed — install backend/requirements-quant.txt")

    df = slice_by_horizon(stock_df, horizon)
    spy = slice_by_horizon(spy_df, horizon)
    if len(df) < 80:
        return _empty(f"Insufficient history for {horizon} horizon")

    in_sample, out_sample = split_in_out_sample(df)
    spy_in, spy_out = split_in_out_sample(spy)

    full_metrics = _run_single_window(
        df,
        spy,
        entry_fn=entry_fn,
        hold_days=hold_days,
        stop_pct=stop_pct,
        target_pct=target_pct,
        initial_capital=initial_capital,
    )
    is_metrics = _run_single_window(
        in_sample,
        spy_in,
        entry_fn=entry_fn,
        hold_days=hold_days,
        stop_pct=stop_pct,
        target_pct=target_pct,
        initial_capital=initial_capital,
    )

    oos_metrics: dict[str, Any] | None = None
    if not out_sample.empty and len(out_sample) >= 60:
        oos_metrics = _run_single_window(
            out_sample,
            spy_out,
            entry_fn=entry_fn,
            hold_days=hold_days,
            stop_pct=stop_pct,
            target_pct=target_pct,
            initial_capital=initial_capital,
        )

    passed = True
    fail_reasons: list[str] = []
    if oos_metrics:
        if oos_metrics.get("sharpe_ratio", 0) <= 0:
            passed = False
            fail_reasons.append("OOS Sharpe <= 0")
        if oos_metrics.get("win_rate_pct", 0) < 40:
            passed = False
            fail_reasons.append("OOS win rate < 40%")
    elif full_metrics.get("trade_count", 0) == 0:
        passed = False
        fail_reasons.append("No trades triggered")

    return {
        "horizon": horizon,
        "strategy_version": strategy_version,
        "backtest_engine": "vectorbt",
        **full_metrics,
        "in_sample": is_metrics,
        "out_of_sample": oos_metrics,
        "validation_passed": passed,
        "validation_notes": fail_reasons,
        "message": "Quantitative backtest (vectorbt) — not investment advice",
    }


def run_multi_horizon_backtest_vectorbt(
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
    results: dict[str, Any] = {}
    for horizon in horizons:
        result = run_backtest_with_oos_vectorbt(
            stock_df,
            spy_df,
            entry_fn=entry_fn,
            horizon=horizon,
            hold_days=hold_days,
            stop_pct=stop_pct,
            target_pct=target_pct,
            strategy_version=strategy_version,
        )
        results[horizon] = result

    passed_count = sum(1 for r in results.values() if r.get("validation_passed"))
    return {
        "horizons": results,
        "overall_passed": passed_count >= len(horizons) // 2 + 1 if results else False,
        "strategy_version": strategy_version,
        "message": "Multi-horizon backtest (vectorbt) — not investment advice",
    }


def _empty(msg: str) -> dict[str, Any]:
    return {
        "initial_capital": 10_000.0,
        "final_capital": 10_000.0,
        "total_return_pct": 0.0,
        "annualized_return_pct": 0.0,
        "buy_hold_return_pct": 0.0,
        "win_rate_pct": 0.0,
        "trade_count": 0,
        "max_drawdown_pct": 0.0,
        "sharpe_ratio": 0.0,
        "validation_passed": False,
        "validation_notes": [msg],
        "trades": [],
        "backtest_engine": "vectorbt",
        "message": msg,
    }

