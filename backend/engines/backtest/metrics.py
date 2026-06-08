"""Portfolio backtest analytics — Sortino, Calmar, beta, alpha."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sortino_ratio(returns: pd.Series, rf: float = 0.0) -> float:
    if returns.empty or len(returns) < 2:
        return 0.0
    excess = returns - rf / 252.0
    downside = excess[excess < 0]
    if len(downside) < 2:
        return 0.0
    dd_std = float(downside.std())
    if dd_std <= 0:
        return 0.0
    return float((excess.mean() / dd_std) * np.sqrt(252))


def calmar_ratio(cagr_pct: float, max_dd_pct: float) -> float:
    if max_dd_pct >= 0:
        return 0.0
    return float(cagr_pct / abs(max_dd_pct))


def beta_alpha(
    port_returns: pd.Series,
    bench_returns: pd.Series,
) -> tuple[float, float]:
    aligned = pd.concat([port_returns, bench_returns], axis=1, join="inner").dropna()
    if len(aligned) < 20:
        return 0.0, 0.0
    p = aligned.iloc[:, 0]
    b = aligned.iloc[:, 1]
    cov = float(np.cov(p, b)[0, 1])
    var_b = float(np.var(b))
    beta = cov / var_b if var_b > 0 else 0.0
    alpha_ann = float((p.mean() - beta * b.mean()) * 252 * 100)
    return round(beta, 3), round(alpha_ann, 2)
