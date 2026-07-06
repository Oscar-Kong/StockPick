"""Extract per-slice factor diagnostics from validation artifacts."""
from __future__ import annotations

from typing import Any

from engines.factor.discovery.validation_models import FactorValidationArtifact
from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
from services.factor_discovery.repositories import FactorDiscoveryRunRepository, FactorValidationArtifactRepository


def _na(value: Any, reason: str) -> dict:
    return {"status": "not_applicable", "reason": reason, "value": None}


def extract_factor_diagnostics(
    artifact: FactorValidationArtifact,
    *,
    sleeve: str,
    slice_id: str,
) -> dict:
    disc = artifact.discovery_metrics or {}
    valid = artifact.validation_metrics or {}
    robust = artifact.robustness or {}
    wf = artifact.walk_forward or {}
    coverage = disc.get("coverage") or valid.get("coverage") or {}

    def metric(key: str, source: dict, *, na_reason: str | None = None):
        if key not in source and na_reason:
            return _na(None, na_reason)
        return {"status": "ok", "value": source.get(key)}

    return {
        "sleeve": sleeve,
        "slice_id": slice_id,
        "factor_id": artifact.factor_id,
        "factor_version": artifact.factor_version,
        "acceptance_status": artifact.acceptance_gate.overall_status,
        "observation_count": metric("valid_date_count", valid, na_reason="no validation IC dates"),
        "symbol_coverage": coverage.get("symbol_count") if coverage else _na(None, "coverage not in artifact"),
        "date_coverage": coverage.get("date_count") if coverage else _na(None, "coverage not in artifact"),
        "missing_value_rate": metric("missing_value_rate", disc, na_reason="missing value rate not reported"),
        "winsorization_rate": metric("winsorization_rate", disc, na_reason="winsorization not reported"),
        "mean_rank_ic": metric("mean_rank_ic", valid),
        "median_rank_ic": metric("median_rank_ic", valid, na_reason="median rank IC not reported separately"),
        "rank_ic_std": metric("rank_ic_std", valid),
        "rank_ic_ir": metric("rank_ic_ir", valid),
        "positive_rank_ic_pct": metric("positive_rank_ic_pct", valid),
        "top_minus_bottom_spread": metric("top_minus_bottom_spread", valid, na_reason="quantile spread not reported"),
        "spread_hit_rate": metric("spread_hit_rate", valid, na_reason="spread hit rate not reported"),
        "monotonicity": metric("quantile_monotonicity", valid, na_reason="monotonicity not reported"),
        "turnover": metric("mean_turnover", valid, na_reason="turnover not reported"),
        "transaction_cost_impact_bps": metric("estimated_cost_drag_bps", valid, na_reason="cost impact not reported"),
        "sector_concentration": robust.get("sector_concentration") or _na(None, "no sector history in staging panel"),
        "market_cap_concentration": robust.get("market_cap_concentration")
        or _na(None, "no market cap history in staging panel"),
        "liquidity_concentration": robust.get("liquidity_concentration")
        or _na(None, "liquidity concentration not reported"),
        "walk_forward_stability": wf or _na(None, "walk-forward not evaluated"),
        "robustness_slices": robust.get("slices") or {},
        "primary_horizon_sessions": artifact.primary_horizon_sessions,
    }


def load_diagnostics_for_run(run_id: str, *, sleeve: str, slice_id: str, verify: bool = True) -> dict:
    runs = FactorDiscoveryRunRepository()
    run = runs.get(run_id)
    if run is None or not run.closed_artifact_hash:
        return {"error": "run_or_artifact_missing", "run_id": run_id}
    row = FactorValidationArtifactRepository().get_by_hash(run.closed_artifact_hash)
    if row is None:
        return {"error": "artifact_not_found", "run_id": run_id}
    artifact = load_and_verify_artifact_record(row) if verify else None
    if artifact is None and verify:
        return {"error": "artifact_integrity_failed", "run_id": run_id}
    if artifact is None:
        from services.research_json import json_loads
        from engines.factor.discovery.validation_models import FactorValidationArtifact as FVA

        artifact = FVA.model_validate(json_loads(row.artifact_json, {}))
    diagnostics = extract_factor_diagnostics(artifact, sleeve=sleeve, slice_id=slice_id)
    diagnostics["run_id"] = run_id
    diagnostics["artifact_id"] = row.artifact_id
    diagnostics["formula_hash"] = artifact.formula_hash
    diagnostics["panel_hash"] = artifact.panel_hash
    return diagnostics
