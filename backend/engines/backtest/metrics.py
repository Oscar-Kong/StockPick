"""Unified backtest performance metrics — shared across all backtest engines."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = 252


def _as_series(values: pd.Series | np.ndarray | list[float], *, name: str = "value") -> pd.Series:
    if isinstance(values, pd.Series):
        return values.astype(float)
    return pd.Series(np.asarray(values, dtype=float), name=name)


def _as_return_series(values: pd.Series | np.ndarray | list[float]) -> pd.Series:
    return _as_series(values, name="return").replace([np.inf, -np.inf], np.nan).dropna()


def sharpe_ratio(
    returns: pd.Series | np.ndarray | list[float],
    *,
    periods_per_year: int = PERIODS_PER_YEAR,
    annualization_factor: float | None = None,
    rf: float = 0.0,
    ddof: int = 0,
) -> float:
    """Annualized Sharpe from per-period simple returns."""
    r = _as_return_series(returns)
    if len(r) < 2:
        return 0.0
    std = float(r.std(ddof=ddof))
    if std <= 0:
        return 0.0
    factor = float(annualization_factor if annualization_factor is not None else np.sqrt(periods_per_year))
    excess = r - rf / periods_per_year if rf else r
    return float((excess.mean() / std) * factor)


def sortino_ratio(
    returns: pd.Series | np.ndarray | list[float],
    *,
    periods_per_year: int = PERIODS_PER_YEAR,
    rf: float = 0.0,
    ddof: int = 1,
) -> float:
    """Annualized Sortino using downside deviation."""
    r = _as_return_series(returns)
    if len(r) < 2:
        return 0.0
    excess = r - rf / periods_per_year
    downside = excess[excess < 0]
    if len(downside) < 2:
        return 0.0
    dd_std = float(downside.std(ddof=ddof))
    if dd_std <= 0:
        return 0.0
    return float((excess.mean() / dd_std) * np.sqrt(periods_per_year))


def max_drawdown(equity: pd.Series | np.ndarray | list[float]) -> float:
    """Maximum drawdown as negative percent (e.g. -12.5)."""
    eq = _as_series(equity, name="equity").dropna()
    if eq.empty:
        return 0.0
    peak = eq.cummax()
    dd = (eq - peak) / peak.replace(0, np.nan)
    return float(dd.min() * 100.0)


def calmar_ratio(cagr_pct: float, max_dd_pct: float) -> float:
    """Calmar = CAGR% / |max drawdown %| when drawdown is negative."""
    if max_dd_pct >= 0:
        return 0.0
    return float(cagr_pct / abs(max_dd_pct))


def annualized_return_pct(
    total_return: float,
    periods: int,
    *,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> float:
    """CAGR% from total simple return over ``periods`` observations."""
    years = max(periods / periods_per_year, 0.01)
    return float(((1.0 + total_return) ** (1.0 / years) - 1.0) * 100.0)


def annualized_volatility_pct(
    returns: pd.Series | np.ndarray | list[float],
    *,
    periods_per_year: int = PERIODS_PER_YEAR,
    ddof: int = 1,
) -> float:
    """Annualized volatility as percent."""
    r = _as_return_series(returns)
    if len(r) < 2:
        return 0.0
    return float(r.std(ddof=ddof) * np.sqrt(periods_per_year) * 100.0)


def win_rate_pct(returns: pd.Series | np.ndarray | list[float]) -> float:
    """Fraction of positive periods/trades as percent (one decimal)."""
    r = _as_return_series(returns)
    if r.empty:
        return 0.0
    return round(float((r > 0).sum() / len(r) * 100.0), 1)


def profit_factor(returns: pd.Series | np.ndarray | list[float]) -> float | None:
    """Gross wins / gross losses; None when no losses."""
    r = _as_return_series(returns)
    if r.empty:
        return None
    wins = r[r > 0].sum()
    losses = abs(float(r[r < 0].sum()))
    if losses <= 0:
        return None
    return round(float(wins / losses), 2)


def turnover_pct(turnover_sum: float) -> float:
    """Convert fractional turnover sum to percent."""
    return round(float(turnover_sum) * 100.0, 2)


def beta_alpha(
    port_returns: pd.Series,
    bench_returns: pd.Series,
) -> tuple[float, float]:
    """OLS beta and annualized alpha% vs benchmark return series."""
    result = benchmark_alpha_beta(port_returns, bench_returns)
    return result["beta"], result["alpha_ann_pct"]


def benchmark_alpha_beta(
    port_returns: pd.Series,
    bench_returns: pd.Series,
    *,
    min_observations: int = 20,
) -> dict[str, float | bool | None]:
    """Beta and annualized alpha when benchmark returns are available."""
    aligned = pd.concat([port_returns, bench_returns], axis=1, join="inner").dropna()
    aligned.columns = ["port", "bench"]
    if len(aligned) < min_observations:
        return {
            "sufficient": False,
            "beta": 0.0,
            "alpha_ann_pct": 0.0,
            "observations": len(aligned),
        }

    p = aligned["port"].astype(float)
    b = aligned["bench"].astype(float)
    cov = float(np.cov(p, b)[0, 1])
    var_b = float(np.var(b))
    beta = cov / var_b if var_b > 0 else 0.0
    alpha_ann = float((p.mean() - beta * b.mean()) * PERIODS_PER_YEAR * 100.0)
    return {
        "sufficient": True,
        "beta": round(beta, 3),
        "alpha_ann_pct": round(alpha_ann, 2),
        "observations": len(aligned),
    }


def summarize_trade_backtest(
    trades: list[dict],
    equity_curve: list[float],
    initial_capital: float,
    hold_days: int,
    benchmark_return_pct: float = 0.0,
) -> dict[str, Any]:
    """
    Metrics for trade-list backtests (``ml/backtest_engine`` shape).

    Preserves legacy field names and rounding.
    """
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

    trade_returns = [float(t["return_pct"]) / 100.0 for t in trades]
    ann_factor = np.sqrt(PERIODS_PER_YEAR / max(hold_days, 1))

    total_days = sum(max(1, t.get("days_held", hold_days)) for t in trades)
    years = max(total_days / PERIODS_PER_YEAR, 0.01)
    ann_return = ((capital / initial_capital) ** (1 / years) - 1) * 100

    return {
        "total_return_pct": round(total_return, 2),
        "gross_return_pct": round(gross_return, 2),
        "annualized_return_pct": round(ann_return, 2),
        "win_rate_pct": win_rate_pct([r * 100 for r in trade_returns]),
        "max_drawdown_pct": round(max_drawdown(equity_curve), 2),
        "sharpe_ratio": round(
            sharpe_ratio(trade_returns, annualization_factor=ann_factor),
            2,
        ),
        "trade_count": len(trades),
        "buy_hold_return_pct": round(benchmark_return_pct, 2),
        "costs_applied": any("gross_return_pct" in t for t in trades),
    }


def summarize_portfolio_backtest(
    equity_series: pd.Series,
    *,
    turnover_sum: float,
    total_return: float,
    periods: int,
    benchmark_returns: pd.Series | None = None,
    include_extended: bool = False,
) -> dict[str, float]:
    """
    Metrics for daily portfolio policy / institutional backtests.

    ``total_return`` is decimal (e.g. 0.12 for +12%).
    """
    port_rets = equity_series.pct_change().dropna()
    ann_ret = annualized_return_pct(total_return, periods)
    max_dd = max_drawdown(equity_series)
    vol = annualized_volatility_pct(port_rets, ddof=1)
    sharpe = sharpe_ratio(port_rets, ddof=1) if len(port_rets) > 1 else 0.0

    out: dict[str, float] = {
        "annualized_return_pct": round(ann_ret, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "volatility_pct": round(vol, 2),
        "sharpe_ratio": round(sharpe, 2),
        "turnover_pct": turnover_pct(turnover_sum),
        "win_rate_pct": win_rate_pct(port_rets),
    }

    pf = profit_factor(port_rets)
    if pf is not None:
        out["profit_factor"] = pf

    if include_extended:
        out["sortino_ratio"] = round(sortino_ratio(port_rets, ddof=1), 2)
        out["calmar_ratio"] = round(calmar_ratio(ann_ret, max_dd), 2)
        if benchmark_returns is not None and len(port_rets) >= 20:
            bench = benchmark_returns.reindex(port_rets.index, method="ffill").dropna()
            ba = benchmark_alpha_beta(port_rets, bench)
            out["beta"] = float(ba["beta"] or 0.0)
            out["alpha_vs_spy_pct"] = float(ba["alpha_ann_pct"] or 0.0)

    return out
