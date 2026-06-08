"""Backtest tear-sheet metrics (quantstats-style, no extra dependency required)."""
from __future__ import annotations

import math
from typing import Any

import numpy as np


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_tear_sheet(result: dict[str, Any]) -> dict[str, Any]:
    """Summarize a single backtest result for UI display."""
    total_return = _safe_float(result.get("total_return_pct"))
    ann_return = _safe_float(result.get("annualized_return_pct"))
    max_dd = _safe_float(result.get("max_drawdown_pct"))
    sharpe = _safe_float(result.get("sharpe_ratio"))
    win_rate = _safe_float(result.get("win_rate_pct"))
    trade_count = int(result.get("trade_count") or 0)
    buy_hold = _safe_float(result.get("buy_hold_return_pct"))

    calmar = None
    if max_dd < 0:
        calmar = round(ann_return / abs(max_dd), 3)

    excess_vs_bh = round(total_return - buy_hold, 2) if buy_hold else None

    trades = result.get("trades") or []
    avg_win = avg_loss = profit_factor = None
    if trades:
        wins = [_safe_float(t.get("return_pct")) for t in trades if _safe_float(t.get("return_pct")) > 0]
        losses = [_safe_float(t.get("return_pct")) for t in trades if _safe_float(t.get("return_pct")) < 0]
        if wins:
            avg_win = round(sum(wins) / len(wins), 2)
        if losses:
            avg_loss = round(sum(losses) / len(losses), 2)
        gross_win = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        if gross_loss > 0:
            profit_factor = round(gross_win / gross_loss, 2)

    oos = result.get("out_of_sample") or {}
    is_ = result.get("in_sample") or {}

    return {
        "total_return_pct": total_return,
        "annualized_return_pct": ann_return,
        "buy_hold_return_pct": buy_hold,
        "excess_return_vs_buy_hold_pct": excess_vs_bh,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe,
        "calmar_ratio": calmar,
        "win_rate_pct": win_rate,
        "trade_count": trade_count,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "profit_factor": profit_factor,
        "validation_passed": result.get("validation_passed"),
        "in_sample_sharpe": is_.get("sharpe_ratio") if isinstance(is_, dict) else None,
        "out_of_sample_sharpe": oos.get("sharpe_ratio") if isinstance(oos, dict) else None,
        "entry_variant": result.get("entry_variant"),
        "backtest_engine": result.get("backtest_engine", "default"),
    }
