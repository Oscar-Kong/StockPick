"""Parameter-sweep overfitting guards (deflated Sharpe, walk-forward proxy)."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from ml.backtest_engine import OOS_SPLIT


def _deflated_sharpe(sharpe: float, n_trials: int, skew: float = 0.0, kurtosis: float = 3.0) -> float:
    """
    Simplified Bailey-López de Prado deflated Sharpe (research guardrail).
    Penalizes Sharpe when many parameter combinations were tested.
    """
    if n_trials <= 1 or sharpe <= 0:
        return sharpe
    # Euler-Mascheroni approx for expected max SR under null
    euler = 0.5772156649
    expected_max = math.sqrt(2 * math.log(n_trials)) * (
        (1 - euler) * 0 + euler * math.sqrt(max(0.0, math.log(math.log(max(n_trials, 2)))))
    )
    variance_sr = (1 + 0.5 * sharpe**2 - skew * sharpe + (kurtosis - 3) / 4 * sharpe**2) / max(
        n_trials, 1
    )
    std_sr = math.sqrt(max(variance_sr, 1e-12))
    z = (sharpe - expected_max) / std_sr if std_sr > 0 else 0.0
    # Normal CDF approximation
    def _phi(x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    return round(sharpe * _phi(z), 4)


def annotate_sweep_results(
    entries: list[dict[str, Any]],
    *,
    n_trials: int,
    walk_forward_windows: int = 3,
) -> dict[str, Any]:
    """
    Add deflated Sharpe to each sweep row and return sweep-level diagnostics.
    Walk-forward proxy: compare top trial OOS validation rate across ranked subset.
    """
    if not entries:
        return {"entries": [], "diagnostics": {}}

    sharpes = [float(e.get("sharpe_ratio") or 0) for e in entries]
    returns = [float(e.get("total_return_pct") or 0) for e in entries]

    for entry in entries:
        sr = float(entry.get("sharpe_ratio") or 0)
        entry["deflated_sharpe"] = _deflated_sharpe(sr, n_trials)

    best = max(entries, key=lambda e: (e.get("deflated_sharpe") or 0, e.get("total_return_pct") or 0))
    median_sharpe = float(np.median(sharpes)) if sharpes else 0.0
    median_return = float(np.median(returns)) if returns else 0.0

    oos_pass_rate = sum(1 for e in entries if e.get("validation_passed")) / len(entries)

    # Walk-forward proxy: split trials into chunks by rank stability
    wf_stable = True
    if len(entries) >= walk_forward_windows * 2:
        chunk = max(1, len(entries) // walk_forward_windows)
        chunk_bests = []
        for i in range(walk_forward_windows):
            subset = entries[i * chunk : (i + 1) * chunk]
            if subset:
                chunk_bests.append(max(subset, key=lambda e: e.get("sharpe_ratio") or 0))
        if len(chunk_bests) >= 2:
            holds = [b.get("hold_days") for b in chunk_bests]
            wf_stable = len(set(holds)) <= 2

    overfit_risk = "low"
    if best.get("sharpe_ratio", 0) > 1.5 and (best.get("deflated_sharpe") or 0) < 0.5:
        overfit_risk = "high"
    elif n_trials > 15 and oos_pass_rate < 0.4:
        overfit_risk = "medium"
    elif not wf_stable:
        overfit_risk = "medium"

    diagnostics = {
        "n_trials": n_trials,
        "median_sharpe": round(median_sharpe, 3),
        "median_return_pct": round(median_return, 2),
        "oos_validation_pass_rate": round(oos_pass_rate, 3),
        "walk_forward_stable": wf_stable,
        "overfit_risk": overfit_risk,
        "oos_split_ratio": OOS_SPLIT,
        "best_deflated_sharpe": best.get("deflated_sharpe"),
        "message": (
            "High deflated Sharpe + OOS pass suggests more robust params. "
            "Low deflated Sharpe after many trials suggests overfitting risk."
        ),
    }
    return {"entries": entries, "diagnostics": diagnostics, "best_by_deflated_sharpe": best}
