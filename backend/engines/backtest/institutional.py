"""Institutional portfolio policy backtest — costs, liquidity, extended metrics."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from config import BT_DELISTING_HAIRCUT, BT_PARTICIPATION_RATE
from data.price_service import PriceService
from engines.backtest.cost_model import trade_cost_usd
from engines.backtest.liquidity import cap_rebalance_notional
from engines.backtest.metrics import summarize_portfolio_backtest
from engines.backtest.universe_pit import active_symbols_on_date, ensure_pit_seeded
from services.policy_backtest import (
    PolicyBacktestResult,
    _build_price_panel,
    _select_weights,
)


@dataclass
class InstitutionalBacktestResult(PolicyBacktestResult):
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    beta: float = 0.0
    alpha_vs_spy_pct: float = 0.0
    total_cost_pct: float = 0.0
    total_cost_usd: float = 0.0
    engine: str = "institutional"
    run_id: str = ""
    cost_events: list[dict[str, Any]] = field(default_factory=list)
    delisted: list[str] = field(default_factory=list)


def run_institutional_policy_backtest(
    symbols: list[str],
    *,
    policy: str = "equal_weight",
    rebalance: str = "monthly",
    top_n: int = 5,
    lookback_period: str = "1y",
    initial_capital: float = 10_000.0,
    max_weight: float = 0.35,
    cash_buffer: float = 0.0,
    sleeve: str | None = "medium",
    fee_bps: float | None = None,
    slip_bps: float | None = None,
    participation_rate: float | None = None,
    use_universe_pit: bool = True,
    persist: bool = False,
) -> InstitutionalBacktestResult:
    symbols = [s.strip().upper() for s in symbols if s and s.strip()]
    symbols = list(dict.fromkeys(symbols))
    if len(symbols) < 2:
        raise ValueError("Need at least 2 symbols for institutional backtest")

    if use_universe_pit:
        ensure_pit_seeded(symbols)

    panel, excluded = _build_price_panel(symbols, lookback_period)
    if panel.empty or len(panel.columns) < 2:
        raise ValueError("Insufficient history for institutional backtest")

    hist_by_sym: dict[str, pd.DataFrame] = {}
    ps = PriceService()
    part_rate = participation_rate if participation_rate is not None else BT_PARTICIPATION_RATE

    returns = panel.pct_change().dropna(how="any")
    step = 5 if rebalance == "weekly" else 21
    lookback = 60
    weights = pd.Series(0.0, index=returns.columns, dtype=float)
    turnover = 0.0
    rebalance_count = 0
    equity = float(initial_capital)
    total_cost = 0.0
    cost_events: list[dict[str, Any]] = []
    delisted: list[str] = []
    equity_rows: list[dict[str, Any]] = []
    weights_rows: list[dict[str, Any]] = []

    for i, date in enumerate(returns.index):
        date_str = date.strftime("%Y-%m-%d")
        active_cols = list(returns.columns)
        if use_universe_pit:
            active_cols = active_symbols_on_date(active_cols, date_str)
            if len(active_cols) < 2:
                active_cols = list(returns.columns)

        if i == 0 or i % step == 0:
            window = returns[active_cols].iloc[max(0, i - lookback) : i + 1]
            if len(window) < 5:
                window = returns[active_cols].iloc[: i + 1]
            new_weights = _select_weights(
                policy=policy,
                returns_window=window,
                max_weight=max_weight,
                cash_buffer=cash_buffer,
                top_n=top_n,
            )
            for c in active_cols:
                if c not in new_weights.index:
                    new_weights[c] = 0.0
            new_weights = new_weights.reindex(active_cols).fillna(0.0)
            if new_weights.sum() > 0:
                new_weights = new_weights / new_weights.sum()
                new_weights = new_weights * max(0.0, 1.0 - cash_buffer)

            delta = (new_weights - weights.reindex(new_weights.index).fillna(0.0)).fillna(0.0)
            turnover += float(delta.abs().sum() / 2.0)
            trade_notional = float(delta.abs().sum() / 2.0) * equity

            capped_notional = 0.0
            for sym in delta.index:
                if abs(delta[sym]) < 1e-8:
                    continue
                if sym not in hist_by_sym:
                    h = ps.get_history(sym, period=lookback_period)
                    hist_by_sym[sym] = h
                price = float(panel[sym].iloc[i]) if sym in panel.columns else 0.0
                desired = float(abs(delta[sym]) * equity)
                exec_n, note = cap_rebalance_notional(
                    sym, desired, price, hist_by_sym.get(sym), participation_rate=part_rate
                )
                capped_notional += exec_n
                if note:
                    cost_events.append({"date": date_str, "note": note})

            cost = trade_cost_usd(capped_notional or trade_notional, fee_bps=fee_bps, slip_bps=slip_bps, sleeve=sleeve)
            total_cost += cost
            if cost > 0:
                equity -= cost
                cost_events.append(
                    {
                        "date": date_str,
                        "notional": round(capped_notional or trade_notional, 2),
                        "cost_usd": round(cost, 2),
                    }
                )
            weights = new_weights
            rebalance_count += 1
            weights_rows.append(
                {
                    "date": date_str,
                    "weights": {k: float(v) for k, v in weights.items() if v > 0},
                }
            )

        day_cols = [c for c in weights.index if c in returns.columns]
        if not day_cols:
            continue
        day_ret = float((weights[day_cols] * returns.iloc[i][day_cols]).sum())
        equity *= 1.0 + day_ret
        equity_rows.append({"date": date_str, "equity": round(equity, 2)})

    for sym in excluded:
        if sym not in delisted:
            delisted.append(sym)

    equity_series = pd.Series([r["equity"] for r in equity_rows], dtype=float)
    if len(equity_rows) >= len(returns):
        equity_series.index = returns.index[: len(equity_rows)]
    total_return = equity / initial_capital - 1.0

    spy = ps.get_spy_history(period=lookback_period)
    benchmark = 0.0
    spy_ret: pd.Series | None = None
    if not spy.empty and len(spy) > 2:
        benchmark = float((float(spy["close"].iloc[-1]) / float(spy["close"].iloc[0]) - 1.0) * 100)
        spy_ret = spy.set_index(pd.to_datetime(spy["date"]))["close"].pct_change().dropna()

    metrics = summarize_portfolio_backtest(
        equity_series,
        turnover_sum=turnover,
        total_return=total_return,
        periods=len(returns),
        benchmark_returns=spy_ret,
        include_extended=True,
    )

    run_id = f"bt-{uuid.uuid4().hex[:12]}"
    notes = [
        f"Institutional sim: fee+slip bps, {part_rate*100:.0f}% ADV cap, delisting haircut {BT_DELISTING_HAIRCUT*100:.0f}% on excluded.",
    ]
    if use_universe_pit:
        notes.append("universe_pit filter applied on rebalance dates when seeded.")

    result = InstitutionalBacktestResult(
        policy=policy,
        rebalance=rebalance,
        lookback_period=lookback_period,
        symbols_used=list(returns.columns),
        excluded=excluded,
        initial_capital=round(initial_capital, 2),
        final_capital=round(equity, 2),
        total_return_pct=round(total_return * 100, 2),
        annualized_return_pct=metrics["annualized_return_pct"],
        max_drawdown_pct=metrics["max_drawdown_pct"],
        volatility_pct=metrics["volatility_pct"],
        sharpe_ratio=metrics["sharpe_ratio"],
        benchmark_return_pct=round(benchmark, 2),
        turnover_pct=metrics["turnover_pct"],
        rebalance_count=rebalance_count,
        equity_curve=equity_rows,
        weights_history=weights_rows,
        notes=notes,
        sortino_ratio=metrics.get("sortino_ratio", 0.0),
        calmar_ratio=metrics.get("calmar_ratio", 0.0),
        beta=metrics.get("beta", 0.0),
        alpha_vs_spy_pct=metrics.get("alpha_vs_spy_pct", 0.0),
        total_cost_pct=round(total_cost / initial_capital * 100, 3),
        total_cost_usd=round(total_cost, 2),
        engine="institutional",
        run_id=run_id,
        cost_events=cost_events[:50],
        delisted=delisted,
    )

    if persist:
        try:
            from engines.backtest.store import persist_backtest_run

            persist_backtest_run(result)
        except Exception:
            pass

    return result
