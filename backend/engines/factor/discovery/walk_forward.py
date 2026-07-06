"""Walk-forward validation for Factor Discovery."""
from __future__ import annotations

from typing import Any

import pandas as pd

from engines.factor.discovery.metrics_adapter import evaluate_cross_sectional_metrics
from engines.factor.discovery.periods import mask_for_sessions
from engines.factor.discovery.portfolio_validation import simulate_long_only_portfolio
from engines.factor.discovery.quantiles import evaluate_quantiles
from engines.factor.discovery.validation_models import FactorValidationConfig


def _fold_sessions(
    sessions: list[str],
    *,
    mode: str,
    train_min: int,
    val_len: int,
    step: int,
) -> list[tuple[list[str], list[str]]]:
    folds: list[tuple[list[str], list[str]]] = []
    if len(sessions) < train_min + val_len:
        return folds
    start = train_min
    while start + val_len <= len(sessions):
        if mode == "expanding":
            train = sessions[:start]
        else:
            train = sessions[max(0, start - train_min) : start]
        val = sessions[start : start + val_len]
        if len(train) >= train_min and len(val) >= 1:
            folds.append((train, val))
        start += step
    return folds


def run_walk_forward_validation(
    scores: pd.Series,
    outcome_panel,
    *,
    discovery_sessions: tuple[str, ...],
    validation_sessions: tuple[str, ...],
    config: FactorValidationConfig,
    direction: str,
) -> dict[str, Any]:
    combined = list(discovery_sessions) + list(validation_sessions)
    folds = _fold_sessions(
        combined,
        mode=config.walk_forward_mode,
        train_min=config.min_discovery_sessions,
        val_len=config.walk_forward_validation_sessions,
        step=config.walk_forward_step_sessions,
    )
    fold_results: list[dict[str, Any]] = []
    pass_count = 0
    for i, (train, val) in enumerate(folds):
        val_mask = mask_for_sessions(scores.index, tuple(val))
        ic = evaluate_cross_sectional_metrics(
            scores,
            outcome_panel,
            period_mask=val_mask,
            config=config,
            direction=direction,
        )
        quant = evaluate_quantiles(
            scores,
            outcome_panel,
            period_mask=val_mask,
            config=config,
            direction=direction,
        )
        port = simulate_long_only_portfolio(
            scores,
            outcome_panel,
            sessions=tuple(val),
            config=config,
            direction=direction,
        )
        mean_ic = ic.get("mean_rank_ic")
        fold_pass = (
            mean_ic is not None
            and mean_ic >= config.min_mean_rank_ic
            and (port.get("net_total_return") or -1) >= 0
        )
        if fold_pass:
            pass_count += 1
        fold_results.append(
            {
                "fold": i + 1,
                "train_start": train[0],
                "train_end": train[-1],
                "val_start": val[0],
                "val_end": val[-1],
                "mean_rank_ic": mean_ic,
                "rank_ic_ir": ic.get("rank_ic_ir"),
                "spread": quant.get("mean_top_minus_bottom_spread"),
                "net_portfolio_return": port.get("net_total_return"),
                "turnover": port.get("mean_turnover_per_rebalance"),
                "coverage": ic.get("valid_date_count"),
                "pass": fold_pass,
            }
        )

    rank_ics = [f["mean_rank_ic"] for f in fold_results if f.get("mean_rank_ic") is not None]
    return {
        "fold_count": len(fold_results),
        "min_folds_required": config.min_walk_forward_folds,
        "fold_pass_rate": round(pass_count / len(fold_results), 4) if fold_results else 0.0,
        "median_mean_rank_ic": sorted(rank_ics)[len(rank_ics) // 2] if rank_ics else None,
        "worst_mean_rank_ic": min(rank_ics) if rank_ics else None,
        "folds": fold_results,
        "sufficient": len(fold_results) >= config.min_walk_forward_folds,
    }
