"""Factor Discovery experiment runner — gated Quant Lab integration."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from config import FACTOR_DISCOVERY_ENABLED
from engines.factor.discovery.compiler import compile_factor_definition
from engines.factor.discovery.executor import compute_factor_panel
from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
from engines.factor.discovery.panel_models import validate_input_panel
from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.validation_engine import validate_factor_execution
from engines.factor.discovery.validation_hashing import validation_config_hash
from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit, FactorDirection, FactorLifecycleStatus
from services.factor_discovery.data_provider import (
    DisabledFactorResearchDataProvider,
    FactorResearchDataProvider,
    get_runtime_factor_research_provider,
)
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.idempotency import launch_payload_hash
from services.factor_discovery.lifecycle_service import FactorLifecycleService
from services.factor_discovery.multiple_testing_service import derive_family_size
from services.factor_discovery.repositories import (
    FactorAttemptLedgerRepository,
    FactorDataSnapshotRepository,
    FactorDefinitionRepository,
    FactorDiscoveryRunRepository,
    FactorResearchFamilyRepository,
    FactorValidationArtifactRepository,
)
from services.factor_discovery.snapshot_service import FactorResearchSnapshotService, SnapshotRequest
from services.research_json import json_dumps, json_loads
from services.research_run_service import notify_run_persisted


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


FACTOR_DISCOVERY_STAGE_ORDER: tuple[str, ...] = (
    "validating_request",
    "loading_factor_definition",
    "compiling_factor",
    "resolving_data_provider",
    "materializing_snapshot",
    "verifying_snapshot",
    "validating_pit_universe",
    "executing_factor",
    "generating_outcomes",
    "resolving_periods",
    "validating_discovery",
    "validating_holdout",
    "running_walk_forward",
    "deriving_multiple_testing_context",
    "evaluating_acceptance",
    "persisting_artifact",
    "indexing_result",
    "complete",
)


@dataclass(frozen=True)
class FactorDiscoveryRunRequest:
    experiment_id: str | None
    job_id: str | None
    factor_id: str
    factor_version: str
    research_family_id: str
    period_split: DiscoveryPeriodSplit
    validation_config: FactorValidationConfig
    created_by: str
    idempotency_key: str | None = None
    declared_family_size: int | None = None
    validation_config_family_id: str = "default_v1"
    snapshot_id: str | None = None


StageCallback = Callable[[str, str, str], None]


class FactorDiscoveryExperimentRunner:
    def __init__(
        self,
        *,
        provider: FactorResearchDataProvider | None = None,
        fixture_builder=None,
        snapshot_service: FactorResearchSnapshotService | None = None,
    ) -> None:
        self._provider = provider or get_runtime_factor_research_provider(fixture_builder=fixture_builder)
        self._snapshots_svc = snapshot_service or FactorResearchSnapshotService()
        self._definitions = FactorDefinitionRepository()
        self._families = FactorResearchFamilyRepository()
        self._runs = FactorDiscoveryRunRepository()
        self._attempts = FactorAttemptLedgerRepository()
        self._snapshots = FactorDataSnapshotRepository()
        self._artifacts = FactorValidationArtifactRepository()
        self._lifecycle = FactorLifecycleService()

    def run(self, req: FactorDiscoveryRunRequest, *, on_stage: StageCallback | None = None) -> dict[str, Any]:
        if not FACTOR_DISCOVERY_ENABLED and isinstance(self._provider, DisabledFactorResearchDataProvider):
            raise FactorDiscoveryError("FACTOR_DISCOVERY_DISABLED", "FACTOR_DISCOVERY_ENABLED is false")

        def stage(name: str, status: str, message: str = "") -> None:
            if on_stage:
                on_stage(name, status, message)
            self._runs.update(run_id, current_stage=name)

        payload_hash = launch_payload_hash(
            factor_id=req.factor_id,
            factor_version=req.factor_version,
            research_family_id=req.research_family_id,
            snapshot_request_identity=None,
            snapshot_id=req.snapshot_id,
            period_split=req.period_split,
            validation_config=req.validation_config,
        )

        if req.idempotency_key:
            existing = self._runs.get_by_idempotency(req.idempotency_key)
            if existing:
                if existing.launch_payload_hash and existing.launch_payload_hash != payload_hash:
                    from services.factor_discovery.errors import IdempotencyConflictError

                    raise IdempotencyConflictError("IDEMPOTENCY_PAYLOAD_MISMATCH", req.idempotency_key)
                return {"run_id": existing.run_id, "status": existing.status, "duplicate": True}

        run_id = f"fdrun_{uuid.uuid4().hex[:12]}"
        self._runs.create(
            run_id=run_id,
            experiment_id=req.experiment_id,
            job_id=req.job_id,
            factor_id=req.factor_id,
            factor_version=req.factor_version,
            research_family_id=req.research_family_id,
            status="running",
            current_stage="validating_request",
            period_split_json=json_dumps(req.period_split.model_dump(mode="json")),
            validation_config_json=json_dumps(req.validation_config.model_dump(mode="json")),
            idempotency_key=req.idempotency_key,
            launch_payload_hash=payload_hash,
            created_by=req.created_by,
            started_at=_utcnow(),
        )
        attempt_id = self._attempts.append(
            run_id=run_id,
            research_family_id=req.research_family_id,
            factor_id=req.factor_id,
            factor_version=req.factor_version,
            attempt_kind="NEW_FORMULA",
            attempt_sequence=1,
            stage_reached="validating_request",
            outcome="pending",
            primary_horizon_sessions=req.validation_config.primary_horizon_sessions,
            validation_config_hash=validation_config_hash(req.validation_config),
        )

        try:
            stage("loading_factor_definition", "running")
            def_row = self._definitions.get(req.factor_id, req.factor_version)
            if def_row is None:
                raise FactorDiscoveryError("FACTOR_DEFINITION_NOT_FOUND", f"{req.factor_id}@{req.factor_version}")
            if def_row.lifecycle_status not in {
                FactorLifecycleStatus.COMPILED.value,
                FactorLifecycleStatus.RESEARCHING.value,
                FactorLifecycleStatus.PROMISING.value,
                FactorLifecycleStatus.VALIDATED.value,
            }:
                raise FactorDiscoveryError(
                    "FACTOR_NOT_COMPILED",
                    f"factor must be at least COMPILED, got {def_row.lifecycle_status}",
                )

            definition = __import__(
                "models.schemas_factor_discovery", fromlist=["FactorDefinition"]
            ).FactorDefinition(
                factor_id=def_row.factor_id,
                version=def_row.version,
                display_name=def_row.display_name,
                hypothesis_id=def_row.hypothesis_id,
                expression=parse_factor_expression(def_row.canonical_dsl),
                expected_direction=FactorDirection(def_row.expected_direction),
                intended_universe="research",
                rebalance_frequency=def_row.rebalance_frequency,
                holding_period_sessions=def_row.holding_period_sessions,
                required_fields=json_loads(def_row.required_fields_json, []),
                data_source_policy_id=def_row.data_source_policy_id,
                missing_value_policy=def_row.missing_value_policy,
                outlier_policy=def_row.outlier_policy,
                lifecycle_status=FactorLifecycleStatus(def_row.lifecycle_status),
                parent_factor_id=def_row.parent_factor_id,
                parent_version=def_row.parent_version,
            )

            stage("compiling_factor", "running")
            registry = build_default_field_registry()
            policy = default_data_source_policy()
            plan = compile_factor_definition(definition, field_registry=registry, data_source_policy=policy)
            if plan.formula_hash_value != def_row.formula_hash:
                raise FactorDiscoveryError("FORMULA_HASH_MISMATCH", "compiled formula hash mismatch")

            stage("resolving_data_provider", "running")
            provider_id = getattr(self._provider, "provider_id", "unknown")
            provider_data_version = getattr(
                getattr(self._provider, "capabilities", lambda: None)(),
                "provider_data_version",
                "fixture_v1",
            ) if hasattr(self._provider, "capabilities") else "fixture_v1"

            stage("materializing_snapshot", "running")
            universe_source = (
                "universe_pit_v1"
                if provider_id == "historical_store_v1"
                else "fixture_universe_v1"
            )
            snap_req = SnapshotRequest(
                provider_id=provider_id,
                data_source_policy_id=definition.data_source_policy_id,
                start_session=str(req.period_split.discovery_start) if req.period_split.discovery_start else None,
                end_session=str(req.period_split.sealed_test_end) if req.period_split.sealed_test_end else None,
                universe_source=universe_source,
                required_fields=frozenset(definition.required_fields or []),
                provider_data_version=provider_data_version or "fixture_v1",
            )
            if req.snapshot_id:
                panel = self._snapshots_svc.load_verified(req.snapshot_id)
                snap_ref_row = self._snapshots.get(req.snapshot_id)
                from services.factor_discovery.data_provider import FactorResearchSnapshotRef

                snap_ref = FactorResearchSnapshotRef(
                    snapshot_id=req.snapshot_id,
                    provider_id=snap_ref_row.provider_id,
                    data_source_policy_id=snap_ref_row.data_source_policy_id,
                    panel_hash=snap_ref_row.panel_hash,
                    canonical_session_hash=snap_ref_row.canonical_session_hash,
                    universe_source=snap_ref_row.universe_source,
                    universe_version=snap_ref_row.universe_version,
                    universe_pit_evidence=json_loads(snap_ref_row.universe_pit_evidence_json, {}),
                    field_list=json_loads(snap_ref_row.field_list_json, []),
                    field_provenance_summary=json_loads(snap_ref_row.field_provenance_summary_json, {}),
                    adjustment_status=snap_ref_row.adjustment_status,
                    start_session=snap_ref_row.start_session,
                    end_session=snap_ref_row.end_session,
                    row_count=snap_ref_row.row_count,
                    symbol_count=snap_ref_row.symbol_count,
                    date_count=snap_ref_row.date_count,
                    storage_reference=snap_ref_row.storage_reference,
                    storage_format=snap_ref_row.storage_format,
                    artifact_present=snap_ref_row.artifact_present,
                )
                snapshot_id = req.snapshot_id
            else:
                snapshot_id, panel, snap_ref = self._snapshots_svc.materialize(
                    self._provider, snap_req, plan=plan
                )

            stage("verifying_snapshot", "running")
            _ = self._snapshots_svc.load_verified(snapshot_id)

            stage("validating_pit_universe", "running")
            validate_input_panel(panel, plan=plan)

            stage("executing_factor", "running")
            execution = compute_factor_panel(plan, panel)

            stage("validating_discovery", "running")
            family = self._families.get(req.research_family_id)
            if family is None:
                raise FactorDiscoveryError("RESEARCH_FAMILY_NOT_FOUND", req.research_family_id)
            if family.closed:
                raise FactorDiscoveryError("RESEARCH_FAMILY_CLOSED", req.research_family_id)

            attempts = self._attempts.list_for_family(req.research_family_id)
            stage("deriving_multiple_testing_context", "running")
            family_size = derive_family_size(
                attempts,
                primary_horizon_sessions=req.validation_config.primary_horizon_sessions,
                validation_config_family_id=family.validation_config_family_id,
                declared_family_size=req.declared_family_size,
            )
            vconfig = req.validation_config.model_copy(
                update={"declared_hypothesis_family_size": family_size.effective_family_size}
            )

            artifact = validate_factor_execution(
                plan=plan,
                execution_result=execution,
                input_panel=panel,
                period_split=req.period_split,
                validation_config=vconfig,
                factor_direction=definition.expected_direction,
                factor_id=definition.factor_id,
                factor_version=definition.version,
            )

            stage("persisting_artifact", "running")
            artifact_id = self._artifacts.create_closed(
                run_id=run_id,
                artifact_schema_version=artifact.schema_version,
                validation_engine_version=artifact.validation_engine_version,
                artifact_json=json_dumps(artifact.model_dump(mode="json")),
                formula_hash=artifact.formula_hash,
                plan_hash=artifact.plan_hash,
                panel_hash=artifact.panel_hash,
                canonical_session_hash=artifact.canonical_session_hash,
                execution_hash=artifact.execution_hash,
                outcome_hashes_json=json_dumps(artifact.outcome_panel_hashes),
                period_hash=artifact.period_resolution_hash,
                validation_config_hash=artifact.validation_config_hash,
                validation_artifact_hash=artifact.validation_artifact_hash,
                acceptance_status=artifact.acceptance_gate.overall_status,
                multiple_testing_method=vconfig.multiple_testing_method,
                declared_family_size=req.declared_family_size,
                derived_family_size=family_size.derived_family_size,
                family_size_at_evaluation=family_size.effective_family_size,
            )

            self._runs.update(
                run_id,
                status="completed",
                current_stage="complete",
                panel_snapshot_id=snapshot_id,
                formula_hash=artifact.formula_hash,
                plan_hash=artifact.plan_hash,
                panel_hash=artifact.panel_hash,
                canonical_session_hash=artifact.canonical_session_hash,
                execution_hash=artifact.execution_hash,
                closed_artifact_hash=artifact.validation_artifact_hash,
                completed_at=_utcnow(),
            )
            self._attempts.append(
                run_id=run_id,
                research_family_id=req.research_family_id,
                factor_id=req.factor_id,
                factor_version=req.factor_version,
                formula_hash=artifact.formula_hash,
                attempt_kind="NEW_FORMULA",
                attempt_sequence=2,
                stage_reached="complete",
                outcome="validation_completed",
                metric_evaluation_started=True,
                primary_horizon_sessions=req.validation_config.primary_horizon_sessions,
                validation_config_hash=artifact.validation_config_hash,
            )

            stage("indexing_result", "running")
            notify_run_persisted(run_id, store="factor_discovery_runs")

            recommendation = self._lifecycle.recommend_status_from_artifact(artifact.acceptance_gate.overall_status)
            if recommendation:
                self._lifecycle.store_recommendation(req.factor_id, req.factor_version, recommendation)
            return {
                "run_id": run_id,
                "attempt_id": attempt_id,
                "artifact_id": artifact_id,
                "status": "completed",
                "acceptance_status": artifact.acceptance_gate.overall_status,
                "recommended_status": recommendation.value if recommendation else None,
                "family_size_at_evaluation": family_size.effective_family_size,
            }
        except FactorDiscoveryError as exc:
            self._fail_run(run_id, req, exc.code, str(exc), attempt_id)
            raise
        except Exception as exc:
            self._fail_run(run_id, req, "RUNNER_FAILURE", str(exc)[:500], attempt_id)
            raise FactorDiscoveryError("RUNNER_FAILURE", str(exc)[:500]) from exc

    def _fail_run(
        self,
        run_id: str,
        req: FactorDiscoveryRunRequest,
        code: str,
        summary: str,
        attempt_id: str,
    ) -> None:
        self._runs.update(
            run_id,
            status="failed",
            error_code=code,
            error_summary=summary[:500],
            completed_at=_utcnow(),
        )
        self._attempts.append(
            run_id=run_id,
            research_family_id=req.research_family_id,
            factor_id=req.factor_id,
            factor_version=req.factor_version,
            attempt_kind="NEW_FORMULA",
            attempt_sequence=99,
            stage_reached="failed",
            outcome=self._outcome_for_code(code),
            error_code=code,
            error_summary=summary[:500],
            primary_horizon_sessions=req.validation_config.primary_horizon_sessions,
            validation_config_hash=validation_config_hash(req.validation_config),
        )
        notify_run_persisted(run_id, store="factor_discovery_runs")

    @staticmethod
    def _outcome_for_code(code: str) -> str:
        mapping = {
            "COMPILE_FAILURE": "compile_failed",
            "FORMULA_HASH_MISMATCH": "compile_failed",
            "FACTOR_NOT_COMPILED": "compile_failed",
            "FACTOR_RESEARCH_DATA_PROVIDER_NOT_CONFIGURED": "panel_failed",
            "EMPTY_PIT_UNIVERSE": "panel_failed",
            "RUNNER_FAILURE": "execution_failed",
            "ARTIFACT_INTEGRITY_FAILURE": "validation_failed",
        }
        return mapping.get(code, "validation_failed")
