"""Versioned promotion gate thresholds — single source of truth."""
from __future__ import annotations

import json
from pathlib import Path

POLICY_ID = "factor_promotion_gates_v1"
POLICY_VERSION = "1.0.0"

_DEFAULT_THRESHOLDS: dict[str, dict] = {
    "sufficient_observations": {
        "display_name": "Sufficient observations",
        "min_valid_validation_dates": 20,
        "blocking": True,
    },
    "sufficient_pit_date_coverage": {
        "display_name": "Sufficient PIT date coverage",
        "min_date_count": 20,
        "blocking": True,
    },
    "sufficient_symbol_coverage": {
        "display_name": "Sufficient symbol coverage",
        "min_symbol_count": 3,
        "blocking": True,
    },
    "positive_stable_oos_ic": {
        "display_name": "Positive stable out-of-sample IC",
        "min_mean_rank_ic": 0.01,
        "blocking": False,
    },
    "acceptable_ic_dispersion": {
        "display_name": "Acceptable IC dispersion",
        "max_rank_ic_std": 0.15,
        "blocking": False,
    },
    "acceptable_top_bottom_spread": {
        "display_name": "Acceptable top-minus-bottom spread",
        "min_spread": 0.0,
        "blocking": False,
    },
    "reasonable_monotonicity": {
        "display_name": "Reasonable quantile monotonicity",
        "min_monotonicity": 0.5,
        "blocking": False,
    },
    "no_leakage_flags": {
        "display_name": "No leakage flags",
        "blocking": True,
    },
    "reproducibility_pass": {
        "display_name": "Reproducibility pass",
        "blocking": True,
    },
    "negative_controls_ok": {
        "display_name": "Negative controls behave as expected",
        "blocking": True,
    },
    "transaction_cost_survivability": {
        "display_name": "Transaction-cost survivability",
        "max_cost_drag_bps": 50.0,
        "blocking": False,
    },
    "turnover_limits": {
        "display_name": "Turnover within limits",
        "max_mean_turnover": 0.8,
        "blocking": False,
    },
    "liquidity_suitability": {
        "display_name": "Liquidity suitability",
        "blocking": False,
    },
    "sector_concentration": {
        "display_name": "Sector concentration acceptable",
        "max_hhi": 0.5,
        "blocking": False,
    },
    "sleeve_consistency": {
        "display_name": "Sleeve consistency",
        "blocking": False,
    },
    "recent_period_degradation": {
        "display_name": "Recent-period degradation acceptable",
        "max_ic_drop": 0.05,
        "blocking": False,
    },
    "baseline_comparison": {
        "display_name": "Comparison against baseline",
        "blocking": False,
    },
}


def load_gate_policy() -> dict:
    path = Path(__file__).resolve().parent / "gate_policy_v1.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "policy_id": data.get("policy_id", POLICY_ID),
            "policy_version": data.get("policy_version", POLICY_VERSION),
            "gates": data.get("gates", _DEFAULT_THRESHOLDS),
        }
    return {"policy_id": POLICY_ID, "policy_version": POLICY_VERSION, "gates": _DEFAULT_THRESHOLDS}
