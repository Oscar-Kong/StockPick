"""UI-ready validation artifact presentation with integrity verification."""
from __future__ import annotations

from datetime import datetime, timezone

from data.db_engine import get_engine
from engines.factor_discovery_models import FactorDiscoveryRun, FactorValidationArtifactRecord
from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
from services.factor_discovery.errors import ArtifactIntegrityError, FactorDiscoveryError
from services.factor_discovery.mining.promising_policy import evaluate_promising
from services.research_json import json_loads
from sqlalchemy.orm import Session


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


class FactorValidationResultService:
    def get_by_artifact_id(self, artifact_id: str, *, verify: bool = True) -> dict:
        with Session(get_engine()) as session:
            row = session.get(FactorValidationArtifactRecord, artifact_id)
            if row is None:
                raise FactorDiscoveryError("ARTIFACT_NOT_FOUND", artifact_id)
            run = session.get(FactorDiscoveryRun, row.run_id)
        return self._build_ui_payload(row, run, verify=verify)

    def get_by_run_id(self, run_id: str, *, verify: bool = True) -> dict:
        with Session(get_engine()) as session:
            run = session.get(FactorDiscoveryRun, run_id)
            if run is None:
                raise FactorDiscoveryError("RUN_NOT_FOUND", run_id)
            row = None
            if run.closed_artifact_hash:
                row = (
                    session.query(FactorValidationArtifactRecord)
                    .filter(FactorValidationArtifactRecord.validation_artifact_hash == run.closed_artifact_hash)
                    .one_or_none()
                )
            if row is None:
                raise FactorDiscoveryError("ARTIFACT_NOT_FOUND", run_id)
        return self._build_ui_payload(row, run, verify=verify)

    def _build_ui_payload(self, row: FactorValidationArtifactRecord, run: FactorDiscoveryRun | None, *, verify: bool) -> dict:
        integrity_status = "NOT_VERIFIED"
        integrity_error_code = None
        integrity_error_summary = None
        integrity_checked_at = None
        artifact = None
        promising_result = None

        if verify:
            try:
                artifact = load_and_verify_artifact_record(row)
                integrity_status = "VERIFIED"
                integrity_checked_at = _utcnow_iso()
                promising_result = evaluate_promising(artifact, integrity_ok=True).model_dump(mode="json")
            except ArtifactIntegrityError as exc:
                integrity_status = "FAILED"
                integrity_error_code = exc.code
                integrity_error_summary = exc.message
                integrity_checked_at = _utcnow_iso()
        else:
            payload = json_loads(row.artifact_json, {})
            from engines.factor.discovery.validation_models import FactorValidationArtifact

            artifact = FactorValidationArtifact.model_validate(payload)
            promising_result = evaluate_promising(artifact, integrity_ok=False).model_dump(mode="json")

        assert artifact is not None
        sealed_opened = artifact.sealed_test.opened
        return {
            "artifact_id": row.artifact_id,
            "run_id": row.run_id,
            "identity": {
                "factor_id": artifact.factor_id or (run.factor_id if run else None),
                "factor_version": artifact.factor_version or (run.factor_version if run else None),
                "formula_hash": artifact.formula_hash,
                "plan_hash": artifact.plan_hash,
                "execution_hash": artifact.execution_hash,
                "validation_artifact_hash": artifact.validation_artifact_hash,
                "snapshot_id": run.panel_snapshot_id if run else None,
                "provider": run.created_by if run else None,
                "primary_horizon_sessions": artifact.primary_horizon_sessions,
                "factor_direction": artifact.factor_direction,
                "artifact_schema_version": artifact.schema_version,
                "validation_engine_version": artifact.validation_engine_version,
            },
            "periods": {
                "discovery": artifact.diagnostics.get("discovery_period"),
                "validation": artifact.diagnostics.get("validation_period"),
                "sealed": artifact.diagnostics.get("sealed_period"),
                "sealed_status": artifact.sealed_test.status,
                "sealed_opened": sealed_opened,
                "embargo": artifact.sealed_test.embargo_sessions if hasattr(artifact.sealed_test, "embargo_sessions") else None,
            },
            "integrity": {
                "integrity_status": integrity_status,
                "integrity_checked_at": integrity_checked_at,
                "integrity_error_code": integrity_error_code,
                "integrity_error_summary": integrity_error_summary,
            },
            "overview": {
                "validation_status": artifact.acceptance_gate.overall_status,
                "promising_status": promising_result.get("promising_for_human_review") if promising_result else False,
                "validation_rank_ic": artifact.validation_metrics.get("mean_rank_ic"),
                "robust_significant": artifact.statistical_results.get("robust_significant"),
                "net_result": artifact.portfolio_results.get("net_return"),
                "turnover": artifact.portfolio_results.get("annualized_turnover"),
                "walk_forward_pass_rate": artifact.walk_forward.get("pass_rate") or artifact.walk_forward.get("fold_pass_rate"),
                "multiple_testing_status": artifact.multiple_testing.get("correction_status"),
                "sealed_status": "unopened" if not sealed_opened else artifact.sealed_test.status,
                "limitations": artifact.limitations,
                "warnings": artifact.warnings,
            },
            "signal": {
                "discovery_rank_ic": artifact.discovery_metrics.get("mean_rank_ic"),
                "validation_rank_ic": artifact.validation_metrics.get("mean_rank_ic"),
                "rank_ic_ir": artifact.validation_metrics.get("rank_ic_ir"),
                "positive_ic_frequency": artifact.validation_metrics.get("positive_ic_frequency"),
                "robust_p_value": artifact.statistical_results.get("robust_p_value"),
                "robust_t_statistic": artifact.statistical_results.get("robust_t_statistic"),
                "coverage": artifact.validation_metrics.get("coverage"),
                "valid_date_count": artifact.validation_metrics.get("valid_date_count"),
                "observation_count": artifact.validation_metrics.get("observation_count"),
                "rank_ic_series": artifact.validation_metrics.get("rank_ic_series"),
            },
            "quantiles": artifact.quantile_results,
            "portfolio": artifact.portfolio_results,
            "walk_forward": artifact.walk_forward,
            "robustness": artifact.robustness,
            "redundancy": artifact.redundancy,
            "statistical": artifact.statistical_results,
            "multiple_testing": {
                **artifact.multiple_testing,
                "family_size_at_evaluation": row.family_size_at_evaluation,
                "current_family_size": row.derived_family_size,
                "staleness_warning": (
                    row.derived_family_size is not None
                    and row.family_size_at_evaluation is not None
                    and row.derived_family_size > row.family_size_at_evaluation
                ),
            },
            "acceptance": artifact.acceptance_gate.model_dump(mode="json"),
            "promising_policy": promising_result,
            "diagnostics": artifact.diagnostics,
            "limitations": artifact.limitations,
            "no_sealed_metrics": not sealed_opened,
            "no_lifecycle_promotion": True,
            "no_production_integration": True,
            "trust_metrics": integrity_status == "VERIFIED",
        }
