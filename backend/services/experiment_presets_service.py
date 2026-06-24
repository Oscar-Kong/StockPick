"""Transparent experiment presets — parameter overrides only, no hidden math changes."""
from __future__ import annotations

from typing import Any

from models.schemas_research import (
    ExperimentPreset,
    ExperimentPresetInfo,
    ExperimentPresetsResponse,
    ExperimentTemplateInfo,
    ExperimentTemplatesResponse,
    ExperimentType,
    PresetParameterValue,
)

SCAN_EVAL_SMOKE_PRESET: dict[str, Any] = {
    "title": "Scan Eval Smoke (MacBook)",
    "description": "Short window, tiny universe, two algorithms — smoke test only, not statistically meaningful.",
    "major_evidence_eligible": False,
    "verdict_ceiling": "exploratory",
    "max_universe": 8,
    "max_symbols": 8,
    "stage_b_cap": 8,
    "max_results": 5,
    "forward_horizons": [5],
    "rebalance_frequency": "monthly",
    "algorithm_versions": ["alphabetical_baseline", "stage_a_v2"],
    "apply_penny_friction": True,
    "spread_bps": 50,
    "slippage_bps": 25,
}

PRESET_ALIASES: dict[str, str] = {
    "exploratory": "quick_check",
    "robust": "robust_validation",
    "scan_eval_smoke": "scan_eval_smoke",
}

BASE_PRESETS: dict[str, dict[str, Any]] = {
    "quick_check": {
        "title": "Quick Check",
        "description": "Lower computation, exploratory verdict ceiling, cannot produce major evidence.",
        "major_evidence_eligible": False,
        "verdict_ceiling": "exploratory",
        "max_symbols": 15,
        "lookback_period": "6mo",
        "forward_horizons": [20],
        "rebalance_frequency": "monthly",
        "min_history_sessions": 60,
        "cost_assumption_bps": 0,
        "slippage_bps": 0,
        "wf_min_periods": 2,
        "pairs_max_pairs": 25,
        "force_ic_refresh": False,
        "institutional_backtest": False,
        "regime_analysis": False,
    },
    "standard_research": {
        "title": "Standard Research",
        "description": "Reasonable history, saved results, out-of-sample checks where supported.",
        "major_evidence_eligible": False,
        "verdict_ceiling": "supporting",
        "max_symbols": 30,
        "lookback_period": "1y",
        "forward_horizons": [20, 60],
        "rebalance_frequency": "monthly",
        "min_history_sessions": 120,
        "cost_assumption_bps": 5,
        "slippage_bps": 5,
        "wf_min_periods": 4,
        "pairs_max_pairs": 50,
        "force_ic_refresh": False,
        "institutional_backtest": True,
        "regime_analysis": True,
    },
    "robust_validation": {
        "title": "Robust Validation",
        "description": "Multiple periods, regime analysis, realistic costs, stronger sample requirements.",
        "major_evidence_eligible": True,
        "verdict_ceiling": "major_review",
        "max_symbols": 50,
        "lookback_period": "2y",
        "forward_horizons": [20, 60, 120],
        "rebalance_frequency": "monthly",
        "min_history_sessions": 252,
        "cost_assumption_bps": 10,
        "slippage_bps": 10,
        "wf_min_periods": 6,
        "pairs_max_pairs": 100,
        "force_ic_refresh": True,
        "institutional_backtest": True,
        "regime_analysis": True,
    },
}

TEMPLATE_META: dict[str, dict[str, Any]] = {
    "factor_validation": {
        "title": "Factor Validation",
        "description": "Validate rank IC, Pearson IC, IR, and horizon/regime breakdowns for selected factors.",
        "required_fields": ["sleeve", "factors"],
        "optional_fields": ["horizons", "start_date", "end_date", "sector_filter", "regime_filter"],
        "universe_sources": ["full_bucket", "latest_scan", "custom_symbols"],
    },
    "walk_forward": {
        "title": "Walk-Forward Ranking Test",
        "description": "Point-in-time walk-forward ranking with turnover and cost metrics.",
        "required_fields": ["sleeve", "start_date", "end_date"],
        "optional_fields": ["horizons", "rebalance_frequency", "max_symbols", "benchmark"],
        "universe_sources": ["full_bucket", "latest_scan", "saved_scan", "custom_symbols"],
    },
    "prediction_calibration": {
        "title": "Prediction Calibration",
        "description": "Resolve outcomes and evaluate forecast error by recommendation and horizon.",
        "required_fields": ["sleeve"],
        "optional_fields": ["symbol", "recommendation", "horizon", "resolution_state", "regime"],
        "universe_sources": ["full_bucket", "latest_scan", "watchlist", "portfolio_holdings"],
    },
    "pairs_discovery": {
        "title": "Pairs Discovery",
        "description": "Cointegration research on a stock universe — not a trade instruction.",
        "required_fields": ["symbols"],
        "optional_fields": ["lookback_period", "zscore_window", "p_value_threshold"],
        "universe_sources": ["custom_symbols", "latest_scan", "watchlist", "portfolio_holdings"],
    },
    "similar_signal": {
        "title": "Similar-Signal Replay",
        "description": "Replay historical analogs for a symbol's current factor profile.",
        "required_fields": ["symbol", "sleeve"],
        "optional_fields": ["forward_days", "regime_filter"],
        "universe_sources": ["custom_symbols"],
    },
    "portfolio_policy": {
        "title": "Portfolio Policy Backtest",
        "description": "Research-only policy simulation — does not create trades or orders.",
        "required_fields": ["symbols", "policy"],
        "optional_fields": ["rebalance", "lookback_period", "fee_bps", "slip_bps", "benchmark"],
        "universe_sources": [
            "portfolio_holdings",
            "watchlist",
            "latest_scan",
            "saved_scan",
            "custom_symbols",
        ],
    },
    "scan_evaluation": {
        "title": "Scan Selection Evaluation",
        "description": "Replay Stage A/B ranking on historical dates and compare forward returns — does not change production scan.",
        "required_fields": ["bucket", "start_date", "end_date", "algorithm_versions"],
        "optional_fields": [
            "rebalance_frequency",
            "forward_horizons",
            "stage_b_cap",
            "max_results",
            "max_universe",
            "spread_bps",
            "slippage_bps",
            "apply_penny_friction",
        ],
        "universe_sources": ["full_bucket"],
    },
}


def normalize_preset(preset: str | None) -> str:
    if not preset or preset == "custom":
        return "custom"
    if preset == "scan_eval_smoke":
        return "scan_eval_smoke"
    return PRESET_ALIASES.get(preset, preset)


def get_preset_parameters(preset: str | None) -> dict[str, Any]:
    key = normalize_preset(preset)
    if key == "custom":
        return {}
    if key == "scan_eval_smoke":
        return {k: v for k, v in SCAN_EVAL_SMOKE_PRESET.items() if k not in ("title", "description", "major_evidence_eligible", "verdict_ceiling")}
    return dict(BASE_PRESETS.get(key, {}))


def merge_parameters(
    experiment_type: str,
    preset: str | None,
    user_params: dict[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    merged.update(get_preset_parameters(preset))
    if user_params:
        merged.update({k: v for k, v in user_params.items() if v is not None})
    if experiment_type == "walk_forward" and "forward_horizons" in merged:
        merged["forward_horizons"] = list(merged["forward_horizons"])
    if experiment_type == "scan_evaluation" and "forward_horizons" in merged:
        merged["forward_horizons"] = [int(x) for x in merged["forward_horizons"]]
    if experiment_type == "scan_evaluation" and "algorithm_versions" in merged:
        av = merged["algorithm_versions"]
        if isinstance(av, str):
            merged["algorithm_versions"] = [v.strip() for v in av.split(",") if v.strip()]
    return merged


def list_presets() -> ExperimentPresetsResponse:
    presets: list[ExperimentPresetInfo] = []
    all_presets = {**BASE_PRESETS, "scan_eval_smoke": SCAN_EVAL_SMOKE_PRESET}
    for preset_id, meta in all_presets.items():
        params = [
            PresetParameterValue(key=k, value=v, description="")
            for k, v in meta.items()
            if k not in ("title", "description", "major_evidence_eligible", "verdict_ceiling")
        ]
        presets.append(
            ExperimentPresetInfo(
                preset_id=preset_id,  # type: ignore[arg-type]
                title=meta["title"],
                description=meta["description"],
                major_evidence_eligible=meta["major_evidence_eligible"],
                verdict_ceiling=meta["verdict_ceiling"],
                parameters=params,
            )
        )
    return ExperimentPresetsResponse(presets=presets)


def list_templates() -> ExperimentTemplatesResponse:
    templates = [
        ExperimentTemplateInfo(
            experiment_type=exp_type,  # type: ignore[arg-type]
            title=meta["title"],
            description=meta["description"],
            required_fields=meta["required_fields"],
            optional_fields=meta["optional_fields"],
            universe_sources=meta["universe_sources"],
        )
        for exp_type, meta in TEMPLATE_META.items()
    ]
    return ExperimentTemplatesResponse(templates=templates)


def preset_allows_major_evidence(preset: str | None) -> bool:
    key = normalize_preset(preset)
    if key == "custom":
        return False
    return bool(BASE_PRESETS.get(key, {}).get("major_evidence_eligible"))
