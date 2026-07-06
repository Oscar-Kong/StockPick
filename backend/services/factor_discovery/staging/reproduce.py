"""Cross-process run reproducibility verification."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from engines.factor.discovery.validation_hashing import validation_artifact_hash
from engines.factor.discovery.validation_models import FactorValidationConfig, FactorValidationArtifact
from models.schemas_factor_discovery import DiscoveryPeriodSplit
from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.repositories import (
    FactorDataSnapshotRepository,
    FactorDefinitionRepository,
    FactorDiscoveryRunRepository,
    FactorValidationArtifactRepository,
)
from services.research_json import json_loads


@dataclass
class RunReproducibilityResult:
    run_id: str
    comparison_status: str
    formula_hash_match: bool
    plan_hash_match: bool
    panel_hash_match: bool
    execution_hash_match: bool
    validation_artifact_hash_match: bool
    artifact_integrity_ok: bool
    details: dict

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "comparison_status": self.comparison_status,
            "formula_hash_match": self.formula_hash_match,
            "plan_hash_match": self.plan_hash_match,
            "panel_hash_match": self.panel_hash_match,
            "execution_hash_match": self.execution_hash_match,
            "validation_artifact_hash_match": self.validation_artifact_hash_match,
            "artifact_integrity_ok": self.artifact_integrity_ok,
            "details": self.details,
        }


class FactorDiscoveryReproduceService:
    """Reload persisted run artifacts and verify identity chains."""

    def verify_run(self, run_id: str, *, compare_run_id: str | None = None) -> RunReproducibilityResult:
        runs = FactorDiscoveryRunRepository()
        run = runs.get(run_id)
        if run is None:
            raise FactorDiscoveryError("RUN_NOT_FOUND", run_id)

        artifacts = FactorValidationArtifactRepository()
        if not run.closed_artifact_hash:
            raise FactorDiscoveryError("ARTIFACT_NOT_FOUND", run_id)
        artifact_row = artifacts.get_by_hash(run.closed_artifact_hash)
        if artifact_row is None:
            raise FactorDiscoveryError("ARTIFACT_NOT_FOUND", run_id)
        artifact = load_and_verify_artifact_record(artifact_row)

        snap_repo = FactorDataSnapshotRepository()
        snap = snap_repo.get(run.panel_snapshot_id) if run.panel_snapshot_id else None

        def_row = FactorDefinitionRepository().get(run.factor_id, run.factor_version)
        period = DiscoveryPeriodSplit.model_validate(json_loads(run.period_split_json, {}))
        vconfig = FactorValidationConfig.model_validate(json_loads(run.validation_config_json, {}))

        recomputed = validation_artifact_hash(
            formula_hash=artifact.formula_hash,
            plan_hash=artifact.plan_hash,
            execution_hash=artifact.execution_hash,
            outcome_hashes=artifact.outcome_panel_hashes,
            period_resolution_hash=artifact.period_resolution_hash,
            validation_config_hash_value=artifact.validation_config_hash,
            sealed_opened=False,
            sealed_access=None,
        )
        validation_hash_match = recomputed == artifact.validation_artifact_hash == artifact_row.validation_artifact_hash

        details = {
            "factor_id": run.factor_id,
            "factor_version": run.factor_version,
            "snapshot_id": run.panel_snapshot_id,
            "snapshot_panel_hash": snap.panel_hash if snap else None,
            "period_split": period.model_dump(mode="json"),
            "validation_config_hash": artifact.validation_config_hash,
            "acceptance_status": artifact_row.acceptance_status,
            "formula_hash": artifact.formula_hash,
            "plan_hash": artifact.plan_hash,
            "execution_hash": artifact.execution_hash,
            "validation_artifact_hash": artifact.validation_artifact_hash,
            "canonical_dsl": def_row.canonical_dsl if def_row else None,
        }

        comparison_status = "EXACT_MATCH"
        formula_match = plan_match = panel_match = execution_match = True

        if compare_run_id:
            other = runs.get(compare_run_id)
            if other is None:
                raise FactorDiscoveryError("RUN_NOT_FOUND", compare_run_id)
            if not other.closed_artifact_hash:
                raise FactorDiscoveryError("ARTIFACT_NOT_FOUND", compare_run_id)
            other_row = artifacts.get_by_hash(other.closed_artifact_hash)
            if other_row is None:
                raise FactorDiscoveryError("ARTIFACT_NOT_FOUND", compare_run_id)
            other_art = load_and_verify_artifact_record(other_row)
            formula_match = run.formula_hash == other.formula_hash == artifact.formula_hash == other_art.formula_hash
            plan_match = run.plan_hash == other.plan_hash == artifact.plan_hash == other_art.plan_hash
            panel_match = run.panel_hash == other.panel_hash == artifact.panel_hash == other_art.panel_hash
            execution_match = (
                run.execution_hash == other.execution_hash == artifact.execution_hash == other_art.execution_hash
            )
            validation_hash_match = (
                validation_hash_match
                and artifact.validation_artifact_hash == other_art.validation_artifact_hash
            )
            if formula_match and plan_match and panel_match and execution_match and validation_hash_match:
                comparison_status = "EXACT_MATCH"
            elif formula_match and plan_match and panel_match and execution_match:
                comparison_status = "SEMANTIC_MATCH_WITH_EXPECTED_CONTEXT_DIFFERENCE"
            else:
                comparison_status = "MISMATCH"
            details["compare_run_id"] = compare_run_id

        return RunReproducibilityResult(
            run_id=run_id,
            comparison_status=comparison_status,
            formula_hash_match=formula_match,
            plan_hash_match=plan_match,
            panel_hash_match=panel_match,
            execution_hash_match=execution_match,
            validation_artifact_hash_match=validation_hash_match,
            artifact_integrity_ok=True,
            details=details,
        )

    @staticmethod
    def identity_fingerprint(run_id: str) -> str:
        runs = FactorDiscoveryRunRepository()
        run = runs.get(run_id)
        if run is None:
            raise FactorDiscoveryError("RUN_NOT_FOUND", run_id)
        payload = {
            "run_id": run_id,
            "formula_hash": run.formula_hash,
            "plan_hash": run.plan_hash,
            "panel_hash": run.panel_hash,
            "execution_hash": run.execution_hash,
            "closed_artifact_hash": run.closed_artifact_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"
