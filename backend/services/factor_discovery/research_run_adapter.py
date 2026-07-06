"""Research Results adapter for Factor Discovery runs."""
from __future__ import annotations

from data.db_engine import get_engine
from engines.factor_discovery_models import FactorDiscoveryRun, FactorValidationArtifactRecord
from models.schemas_research import ResearchRunSummary
from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
from services.research_json import json_loads
from sqlalchemy.orm import Session


def adapter_factor_discovery(run_id: str, row: FactorDiscoveryRun | None = None) -> ResearchRunSummary | None:
    engine = get_engine()
    with Session(engine) as session:
        if row is None:
            row = session.get(FactorDiscoveryRun, run_id)
        if row is None:
            return None

        artifact_row = None
        if row.closed_artifact_hash:
            artifact_row = (
                session.query(FactorValidationArtifactRecord)
                .filter(FactorValidationArtifactRecord.validation_artifact_hash == row.closed_artifact_hash)
                .one_or_none()
            )

    metrics: list[dict] = []
    warnings: list[str] = []
    acceptance = None
    mean_ic = None
    spread = None
    wf_pass = None
    turnover = None
    sealed_status = "SEALED"

    if artifact_row:
        try:
            artifact = load_and_verify_artifact_record(artifact_row)
            acceptance = artifact.acceptance_gate.overall_status
            mean_ic = artifact.validation_metrics.get("mean_rank_ic")
            spread = artifact.portfolio_results.get("cost_adjusted_spread") or artifact.portfolio_results.get(
                "mean_spread"
            )
            wf_pass = artifact.walk_forward.get("fold_pass_rate")
            turnover = artifact.portfolio_results.get("mean_turnover_per_rebalance")
            sealed_status = artifact.sealed_test.status
            warnings = list(artifact.warnings)
        except Exception as exc:
            warnings.append(f"artifact_integrity: {exc}")

    status = row.status
    verdict = acceptance or ("failed" if status == "failed" else "inconclusive")
    primary_metrics = [
        item
        for item in [
            {"name": "mean_validation_rank_ic", "value": mean_ic},
            {"name": "validation_spread", "value": spread},
            {"name": "walk_forward_pass_rate", "value": wf_pass},
            {"name": "turnover", "value": turnover},
            {
                "name": "family_size_at_evaluation",
                "value": artifact_row.family_size_at_evaluation if artifact_row else None,
            },
        ]
        if item["value"] is not None
    ]

    return ResearchRunSummary(
        run_id=run_id,
        experiment_id=row.experiment_id,
        idea_id=None,
        run_type="factor_discovery",
        name=f"Factor Discovery {row.factor_id}@{row.factor_version}",
        status=status,
        verdict=verdict,
        evidence_impact="informational",
        sleeve=None,
        universe=[],
        parameters={
            "factor_id": row.factor_id,
            "factor_version": row.factor_version,
            "research_family_id": row.research_family_id,
            "formula_hash": row.formula_hash,
            "primary_horizon": json_loads(row.validation_config_json, {}).get("primary_horizon_sessions"),
            "sealed_test_status": sealed_status,
            "acceptance_status": acceptance,
            "panel_snapshot_id": row.panel_snapshot_id,
        },
        strategy_version="",
        factor_model_version="",
        data_cutoff=None,
        sample_size=None,
        primary_metrics=primary_metrics,
        warnings=warnings,
        blockers=[row.error_code] if row.error_code else [],
        result_reference={"store": "factor_discovery_runs", "run_id": run_id},
        started_at=row.started_at,
        completed_at=row.completed_at,
    )
