"""Compounder bucket backtest — quality + trend hold."""
from __future__ import annotations

from typing import Any

import pandas as pd

from config import VBT_ENABLED
from data.strategy_registry import StrategyRegistry
from ml.backtest_engine import run_backtest_with_oos, run_multi_horizon_backtest
from ml.backtest_vectorbt import run_backtest_with_oos_vectorbt, run_multi_horizon_backtest_vectorbt
from ml.entry_strategies import get_entry_fn
from scoring.fundamental import revenue_eps_consistency_score, roic_margin_stability_score


def run_compounder_backtest(
    stock_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    info: dict | None = None,
    fundamentals: dict | None = None,
    initial_capital: float = 10_000.0,
    horizon: str = "5y",
    multi_horizon: bool = False,
    engine: str = "default",
    hold_days_override: int | None = None,
    stop_pct_override: float | None = None,
    target_pct_override: float | None = None,
    entry_variant: str | None = None,
) -> dict[str, Any]:
    strategy = StrategyRegistry().get_active("compounder")
    entry_fn, resolved_variant = get_entry_fn(
        "compounder",
        entry_variant,
        info=info,
        fundamentals=fundamentals,
    )
    bt = strategy.backtest_params
    hold_days = int(hold_days_override if hold_days_override is not None else bt.get("hold_days", 252))
    stop_pct = float(stop_pct_override if stop_pct_override is not None else bt.get("stop_pct", 0.20))
    target_pct = target_pct_override if target_pct_override is not None else bt.get("target_pct")
    version = strategy.version_id

    quality_note = None
    if info and fundamentals:
        rev = revenue_eps_consistency_score(info, fundamentals)
        roic = roic_margin_stability_score(info, fundamentals)
        if rev < 50 or roic < 50:
            quality_note = "Fundamental quality below threshold at snapshot"

    use_vectorbt = engine == "vectorbt" and VBT_ENABLED

    if multi_horizon:
        runner = run_multi_horizon_backtest_vectorbt if use_vectorbt else run_multi_horizon_backtest
        result = runner(
            stock_df,
            spy_df,
            entry_fn=entry_fn,
            horizons=["3y", "5y"],
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
        if quality_note:
            notes = list(result.get("validation_notes") or [])
            if quality_note not in notes:
                notes.append(quality_note)
            result["validation_notes"] = notes
    return result
