"""Penny bucket backtest — momentum + volume entry rules."""
from __future__ import annotations

from typing import Any

import pandas as pd

from config import VBT_ENABLED
from data.strategy_registry import StrategyRegistry
from ml.backtest_engine import run_backtest_with_oos, run_multi_horizon_backtest
from ml.backtest_vectorbt import run_backtest_with_oos_vectorbt, run_multi_horizon_backtest_vectorbt
from ml.entry_strategies import get_entry_fn


def run_penny_backtest(
    stock_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    initial_capital: float = 10_000.0,
    horizon: str = "1y",
    multi_horizon: bool = False,
    engine: str = "default",
    hold_days_override: int | None = None,
    stop_pct_override: float | None = None,
    target_pct_override: float | None = None,
    entry_variant: str | None = None,
) -> dict[str, Any]:
    strategy = StrategyRegistry().get_active("penny")
    entry_fn, resolved_variant = get_entry_fn("penny", entry_variant)
    bt = strategy.backtest_params
    hold_days = int(hold_days_override if hold_days_override is not None else bt.get("hold_days", 10))
    stop_pct = float(stop_pct_override if stop_pct_override is not None else bt.get("stop_pct", 0.10))
    target_pct = target_pct_override if target_pct_override is not None else bt.get("target_pct", 0.15)
    version = strategy.version_id

    use_vectorbt = engine == "vectorbt" and VBT_ENABLED

    if multi_horizon:
        runner = run_multi_horizon_backtest_vectorbt if use_vectorbt else run_multi_horizon_backtest
        result = runner(
            stock_df,
            spy_df,
            entry_fn=entry_fn,
            horizons=["1y", "3y"],
            hold_days=hold_days,
            stop_pct=stop_pct,
            target_pct=target_pct,
            strategy_version=version,
        )
    else:
        runner = run_backtest_with_oos_vectorbt if use_vectorbt else run_backtest_with_oos
        result = runner(
            stock_df,
            spy_df,
            entry_fn=entry_fn,
            horizon=horizon,
            hold_days=hold_days,
            stop_pct=stop_pct,
            target_pct=target_pct,
            initial_capital=initial_capital,
            strategy_version=version,
        )
    if isinstance(result, dict):
        result["entry_variant"] = resolved_variant
    return result
