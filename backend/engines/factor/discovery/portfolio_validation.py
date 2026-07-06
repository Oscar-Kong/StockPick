"""Research portfolio simulation for Factor Discovery validation."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engines.backtest.metrics import max_drawdown, sharpe_ratio
from engines.factor.discovery.validation_models import FactorValidationConfig
from services.walk_forward_research_service import turnover_rate


def _rebalance_dates(sessions: list[str], every: int) -> list[str]:
    if every <= 0:
        return sessions
    return sessions[::every]


def simulate_long_only_portfolio(
    scores: pd.Series,
    outcome_panel,
    *,
    sessions: tuple[str, ...],
    config: FactorValidationConfig,
    direction: str,
) -> dict[str, Any]:
    from engines.factor.discovery.metrics_adapter import orient_factor_scores

    oriented = orient_factor_scores(scores, direction=direction)
    reb_dates = _rebalance_dates(list(sessions), config.rebalance_every_sessions)
    if not reb_dates:
        return {"sufficient": False, "reason": "no_rebalance_dates"}

    gross_returns: list[float] = []
    net_returns: list[float] = []
    turnovers: list[float] = []
    holdings_counts: list[int] = []
    prev_holdings: set[str] | None = None
    missing_exec = 0

    for rb in reb_dates:
        ts = pd.Timestamp(rb)
        try:
            day_scores = oriented.xs(ts, level=0)
        except KeyError:
            continue
        day_fwd = outcome_panel.forward_return.xs(ts, level=0)
        day_valid = outcome_panel.outcome_valid.xs(ts, level=0)
        day_elig = outcome_panel.eligibility_at_score.xs(ts, level=0)
        candidates = day_scores[day_elig & day_valid & day_scores.notna() & day_fwd.notna()]
        if candidates.empty:
            missing_exec += 1
            continue
        k = max(1, int(len(candidates) * config.top_quantile_fraction))
        top = candidates.nlargest(k)
        weights = pd.Series(1.0 / len(top), index=top.index)
        if config.max_position_weight < 1.0:
            weights = weights.clip(upper=config.max_position_weight)
            weights = weights / weights.sum()
        port_ret = float((weights * day_fwd.loc[top.index]).sum())
        gross_returns.append(port_ret)
        holdings = set(top.index.astype(str))
        holdings_counts.append(len(holdings))
        t = 0.0 if prev_holdings is None else turnover_rate(prev_holdings, holdings)
        turnovers.append(t)
        cost = config.one_way_cost_bps / 10000.0 * t
        net_returns.append(port_ret - cost)
        prev_holdings = holdings

    if not gross_returns:
        return {"sufficient": False, "reason": "no_portfolio_returns"}

    gross_eq = np.cumprod(1 + np.array(gross_returns))
    net_eq = np.cumprod(1 + np.array(net_returns))
    ann_factor = 252 / max(config.rebalance_every_sessions, 1)
    gross_ann = float((gross_eq[-1] ** (ann_factor / len(gross_returns)) - 1)) if gross_returns else 0.0
    net_ann = float((net_eq[-1] ** (ann_factor / len(net_returns)) - 1)) if net_returns else 0.0
    vol = float(np.std(net_returns, ddof=0) * np.sqrt(ann_factor)) if len(net_returns) > 1 else 0.0

    return {
        "sufficient": True,
        "execution_timing": config.execution_timing,
        "cost_model_id": config.cost_model_id,
        "one_way_cost_bps": config.one_way_cost_bps,
        "turnover_convention": config.turnover_convention,
        "gross_total_return": round(float(gross_eq[-1] - 1), 6),
        "net_total_return": round(float(net_eq[-1] - 1), 6),
        "gross_annualized_return": round(gross_ann, 6),
        "net_annualized_return": round(net_ann, 6),
        "annualized_volatility": round(vol, 6),
        "sharpe_ratio": round(sharpe_ratio(net_returns, periods_per_year=int(ann_factor)), 4),
        "max_drawdown_pct": round(max_drawdown(net_eq), 4),
        "mean_turnover_per_rebalance": round(float(np.mean(turnovers)), 4),
        "annualized_turnover": round(float(np.mean(turnovers)) * ann_factor, 4),
        "estimated_total_costs": round(
            sum(config.one_way_cost_bps / 10000.0 * t for t in turnovers), 6
        ),
        "hit_rate": round(float(np.mean(np.array(net_returns) > 0)), 4),
        "rebalance_count": len(gross_returns),
        "avg_holdings": round(float(np.mean(holdings_counts)), 2),
        "missing_execution_count": missing_exec,
        "concentration_max_weight": config.max_position_weight,
    }
