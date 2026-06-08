"""Portfolio policy backtesting (equal-weight, inverse-vol, top-N momentum)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from data.price_service import PriceService


@dataclass
class PolicyBacktestResult:
    policy: str
    rebalance: str
    lookback_period: str
    symbols_used: list[str]
    excluded: list[str]
    initial_capital: float
    final_capital: float
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    volatility_pct: float
    sharpe_ratio: float
    benchmark_return_pct: float
    turnover_pct: float
    rebalance_count: int
    equity_curve: list[dict[str, Any]]
    weights_history: list[dict[str, Any]]
    notes: list[str]


def _build_price_panel(symbols: list[str], period: str) -> tuple[pd.DataFrame, list[str]]:
    ps = PriceService()
    series: dict[str, pd.Series] = {}
    excluded: list[str] = []
    for symbol in symbols:
        hist = ps.get_history(symbol, period=period)
        if hist.empty or len(hist) < 80:
            excluded.append(symbol)
            continue
        s = hist[["date", "close"]].copy()
        s["date"] = pd.to_datetime(s["date"])
        s = s.dropna().drop_duplicates(subset=["date"])
        if len(s) < 80:
            excluded.append(symbol)
            continue
        series[symbol] = s.set_index("date")["close"].astype(float)
    if not series:
        return pd.DataFrame(), excluded
    panel = pd.concat(series, axis=1).sort_index().ffill().dropna(how="any")
    panel = panel.loc[:, panel.nunique() > 1]
    missing = [s for s in symbols if s not in panel.columns]
    excluded.extend(missing)
    return panel, sorted(set(excluded))


def _select_weights(
    policy: str,
    returns_window: pd.DataFrame,
    max_weight: float,
    cash_buffer: float,
    top_n: int,
) -> pd.Series:
    cols = list(returns_window.columns)
    if not cols:
        return pd.Series(dtype=float)

    if policy == "inverse_vol":
        vol = returns_window.std().replace(0, np.nan)
        raw = (1.0 / vol).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    elif policy == "top_n_momentum":
        momentum = (1.0 + returns_window).prod() - 1.0
        top = momentum.sort_values(ascending=False).head(max(1, min(top_n, len(momentum)))).index
        raw = pd.Series(0.0, index=cols, dtype=float)
        raw.loc[list(top)] = 1.0
    else:
        raw = pd.Series(1.0, index=cols, dtype=float)

    raw = raw.clip(lower=0.0)
    if raw.sum() <= 0:
        raw = pd.Series(1.0, index=cols, dtype=float)
    w = raw / raw.sum()
    w = w.clip(upper=max_weight)
    if w.sum() <= 0:
        w = pd.Series(1.0 / len(cols), index=cols, dtype=float)
    w = w / w.sum()
    w = w * max(0.0, 1.0 - cash_buffer)
    return w


def _max_drawdown_pct(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0, np.nan)
    return float(dd.min() * 100) if len(dd) else 0.0


def _annualized_return_pct(total_return: float, periods: int) -> float:
    years = max(periods / 252.0, 0.01)
    return float(((1.0 + total_return) ** (1.0 / years) - 1.0) * 100.0)


def run_policy_backtest(
    symbols: list[str],
    *,
    policy: str = "equal_weight",
    rebalance: str = "monthly",
    top_n: int = 5,
    lookback_period: str = "1y",
    initial_capital: float = 10_000.0,
    max_weight: float = 0.35,
    cash_buffer: float = 0.0,
) -> PolicyBacktestResult:
    symbols = [s.strip().upper() for s in symbols if s and s.strip()]
    symbols = list(dict.fromkeys(symbols))
    if len(symbols) < 2:
        raise ValueError("Need at least 2 symbols for portfolio policy backtest")

    panel, excluded = _build_price_panel(symbols, lookback_period)
    if panel.empty or len(panel.columns) < 2:
        raise ValueError("Insufficient history to run portfolio policy backtest")

    returns = panel.pct_change().dropna(how="any")
    if returns.empty:
        raise ValueError("No return series available for policy backtest")

    step = 5 if rebalance == "weekly" else 21
    lookback = 60
    weights = pd.Series(0.0, index=returns.columns, dtype=float)
    turnover = 0.0
    rebalance_count = 0
    equity = float(initial_capital)
    equity_rows: list[dict[str, Any]] = []
    weights_rows: list[dict[str, Any]] = []

    for i, date in enumerate(returns.index):
        if i == 0 or i % step == 0:
            window = returns.iloc[max(0, i - lookback) : i + 1]
            if len(window) < 5:
                window = returns.iloc[: i + 1]
            new_weights = _select_weights(
                policy=policy,
                returns_window=window,
                max_weight=max_weight,
                cash_buffer=cash_buffer,
                top_n=top_n,
            )
            turnover += float((new_weights - weights).abs().sum() / 2.0)
            weights = new_weights
            rebalance_count += 1
            weights_rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "weights": {k: float(v) for k, v in weights.items() if v > 0},
                }
            )

        day_ret = float((weights * returns.iloc[i]).sum())
        equity *= (1.0 + day_ret)
        equity_rows.append({"date": date.strftime("%Y-%m-%d"), "equity": round(equity, 2)})

    equity_series = pd.Series([row["equity"] for row in equity_rows], index=returns.index, dtype=float)
    port_rets = equity_series.pct_change().dropna()
    total_return = equity / initial_capital - 1.0
    ann_ret = _annualized_return_pct(total_return, len(returns))
    vol = float(port_rets.std() * np.sqrt(252) * 100) if len(port_rets) > 1 else 0.0
    sharpe = float((port_rets.mean() / port_rets.std()) * np.sqrt(252)) if len(port_rets) > 1 and port_rets.std() > 0 else 0.0

    ps = PriceService()
    spy = ps.get_spy_history(period=lookback_period)
    benchmark = 0.0
    if not spy.empty and len(spy) > 2:
        benchmark = float((float(spy["close"].iloc[-1]) / float(spy["close"].iloc[0]) - 1.0) * 100)

    return PolicyBacktestResult(
        policy=policy,
        rebalance=rebalance,
        lookback_period=lookback_period,
        symbols_used=list(returns.columns),
        excluded=excluded,
        initial_capital=round(initial_capital, 2),
        final_capital=round(equity, 2),
        total_return_pct=round(total_return * 100, 2),
        annualized_return_pct=round(ann_ret, 2),
        max_drawdown_pct=round(_max_drawdown_pct(equity_series), 2),
        volatility_pct=round(vol, 2),
        sharpe_ratio=round(sharpe, 2),
        benchmark_return_pct=round(benchmark, 2),
        turnover_pct=round(turnover * 100, 2),
        rebalance_count=rebalance_count,
        equity_curve=equity_rows,
        weights_history=weights_rows,
        notes=["Policy simulation only — excludes fees/slippage/taxes."],
    )

