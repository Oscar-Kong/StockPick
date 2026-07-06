"""Durable sealed-test access flow for Factor Discovery."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from engines.factor.discovery.metrics_adapter import evaluate_cross_sectional_metrics
from engines.factor.discovery.outcomes import build_factor_outcomes
from engines.factor.discovery.periods import mask_for_sessions, resolve_research_periods
from engines.factor.discovery.sealed_test import sealed_test_receipt_hash, validate_sealed_test_access
from engines.factor.discovery.session_hashing import canonical_session_hash
from engines.factor.discovery.sessions import align_panel_to_canonical_sessions
from engines.factor.discovery.validation_engine import validate_factor_execution
from engines.factor.discovery.validation_hashing import validation_config_hash
from engines.factor.discovery.validation_models import FactorValidationConfig, SealedTestAccess
from models.schemas_factor_discovery import DiscoveryPeriodSplit, FactorDirection
from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
from services.factor_discovery.data_provider import get_runtime_factor_research_provider
from services.factor_discovery.errors import FactorDiscoveryError, SealedTestReservationError
from services.factor_discovery.repositories import (
    FactorDiscoveryRunRepository,
    FactorSealedReceiptRepository,
    FactorValidationArtifactRepository,
)
from services.research_json import json_dumps, json_loads


@dataclass(frozen=True)
class SealedOpenRequest:
    run_id: str
    access: SealedTestAccess
    sealed_data_commitment_hash: str


class FactorSealedTestService:
    def __init__(self, *, fixture_builder=None) -> None:
        self._runs = FactorDiscoveryRunRepository()
        self._artifacts = FactorValidationArtifactRepository()
        self._receipts = FactorSealedReceiptRepository()
        self._provider = get_runtime_factor_research_provider(fixture_builder=fixture_builder)

    def open_sealed_test(self, req: SealedOpenRequest) -> dict:
        run = self._runs.get(req.run_id)
        if run is None or not run.closed_artifact_hash:
            raise FactorDiscoveryError("RUN_NOT_FOUND", req.run_id)

        closed = self._artifacts.get_by_hash(run.closed_artifact_hash)
        if closed is None:
            raise FactorDiscoveryError("CLOSED_ARTIFACT_NOT_FOUND", run.closed_artifact_hash)

        closed_artifact = load_and_verify_artifact_record(closed)
        validate_sealed_test_access(
            req.access,
            formula_hash=closed_artifact.formula_hash,
            plan_hash=closed_artifact.plan_hash,
        )

        identity = {
            "factor_id": run.factor_id,
            "factor_version": run.factor_version,
            "formula_hash": closed_artifact.formula_hash,
            "plan_hash": closed_artifact.plan_hash,
            "panel_snapshot_id": run.panel_snapshot_id or "",
            "period_hash": closed_artifact.period_resolution_hash,
            "validation_config_hash": closed_artifact.validation_config_hash,
            "access_policy_version": req.access.access_policy_version,
            "closed_artifact_hash": closed.validation_artifact_hash,
            "sealed_data_commitment_hash": req.sealed_data_commitment_hash,
            "run_id": req.run_id,
            "approval_reference": req.access.approval_reference,
            "requested_by": req.access.requested_by,
            "reason": req.access.reason,
        }

        try:
            receipt_id = self._receipts.reserve(**identity)
        except FactorDiscoveryError as exc:
            if exc.code in {"SEALED_TEST_ALREADY_OPENED", "SEALED_TEST_ALREADY_RESERVED"}:
                raise SealedTestReservationError(exc.code, exc.message) from exc
            raise

        existing_failed = self._receipts.get(receipt_id)
        if existing_failed and getattr(existing_failed, "status", None) == "FAILED":
            raise FactorDiscoveryError(
                "SEALED_RECEIPT_FAILED",
                "sealed receipt failed; manual recovery authorization required",
            )

        try:
            from services.factor_discovery.snapshot_service import FactorResearchSnapshotService

            panel = FactorResearchSnapshotService().load_verified(run.panel_snapshot_id)
            aligned, calendar, _ = align_panel_to_canonical_sessions(panel)
            session_hash = canonical_session_hash(calendar)
            if session_hash != closed_artifact.canonical_session_hash:
                raise FactorDiscoveryError("SESSION_HASH_MISMATCH", "panel session hash mismatch")

            period_split = DiscoveryPeriodSplit.model_validate(json_loads(run.period_split_json, {}))
            vconfig = FactorValidationConfig.model_validate(json_loads(run.validation_config_json, {}))
            periods = resolve_research_periods(
                period_split,
                calendar,
                config=vconfig,
                canonical_session_hash_value=session_hash,
            )

            from engines.factor.discovery.compiler import compile_factor_definition
            from engines.factor.discovery.executor import compute_factor_panel
            from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
            from engines.factor.discovery.parser import parse_factor_expression
            from models.schemas_factor_discovery import FactorDefinition, FactorLifecycleStatus
            from services.factor_discovery.repositories import FactorDefinitionRepository

            def_row = FactorDefinitionRepository().get(run.factor_id, run.factor_version)
            if def_row is None:
                raise FactorDiscoveryError("FACTOR_DEFINITION_NOT_FOUND", f"{run.factor_id}@{run.factor_version}")
            definition = FactorDefinition(
                factor_id=def_row.factor_id,
                version=def_row.version,
                display_name=def_row.display_name,
                expression=parse_factor_expression(def_row.canonical_dsl),
                expected_direction=FactorDirection(def_row.expected_direction),
                intended_universe="research",
                rebalance_frequency=def_row.rebalance_frequency,
                holding_period_sessions=def_row.holding_period_sessions,
                data_source_policy_id=def_row.data_source_policy_id,
                missing_value_policy=def_row.missing_value_policy,
                outlier_policy=def_row.outlier_policy,
                lifecycle_status=FactorLifecycleStatus(def_row.lifecycle_status),
            )
            plan = compile_factor_definition(
                definition,
                field_registry=build_default_field_registry(),
                data_source_policy=default_data_source_policy(),
            )
            execution = compute_factor_panel(plan, panel)
            primary = vconfig.primary_horizon_sessions
            outcome = build_factor_outcomes(
                aligned,
                horizon_sessions=primary,
                config=vconfig,
                calendar=calendar,
                canonical_session_hash_value=session_hash,
            )
            sealed_mask = mask_for_sessions(execution.factor_values.index, periods.sealed_test_sessions)
            sealed_metrics = evaluate_cross_sectional_metrics(
                execution.factor_values,
                outcome,
                period_mask=sealed_mask,
                config=vconfig,
                direction=definition.expected_direction.value,
            )

            opened_artifact = validate_factor_execution(
                plan=plan,
                execution_result=execution,
                input_panel=panel,
                period_split=period_split,
                validation_config=vconfig,
                factor_direction=definition.expected_direction,
                sealed_test_access=req.access,
                factor_id=definition.factor_id,
                factor_version=definition.version,
            )

            opened_id = self._artifacts.create_opened(
                closed_artifact_id=closed.artifact_id,
                run_id=req.run_id,
                artifact_schema_version=opened_artifact.schema_version,
                validation_engine_version=opened_artifact.validation_engine_version,
                artifact_json=json_dumps(opened_artifact.model_dump(mode="json")),
                formula_hash=opened_artifact.formula_hash,
                plan_hash=opened_artifact.plan_hash,
                panel_hash=opened_artifact.panel_hash,
                canonical_session_hash=opened_artifact.canonical_session_hash,
                execution_hash=opened_artifact.execution_hash,
                outcome_hashes_json=json_dumps(opened_artifact.outcome_panel_hashes),
                period_hash=opened_artifact.period_resolution_hash,
                validation_config_hash=opened_artifact.validation_config_hash,
                validation_artifact_hash=opened_artifact.validation_artifact_hash,
                acceptance_status=opened_artifact.acceptance_gate.overall_status,
                multiple_testing_method=vconfig.multiple_testing_method,
                declared_family_size=closed.declared_family_size,
                derived_family_size=closed.derived_family_size,
                family_size_at_evaluation=closed.family_size_at_evaluation,
            )
            self._receipts.complete(receipt_id, opened_artifact_id=opened_id)
            self._runs.update(req.run_id, opened_artifact_hash=opened_artifact.validation_artifact_hash)
            return {
                "receipt_id": receipt_id,
                "opened_artifact_id": opened_id,
                "sealed_metrics": sealed_metrics,
            }
        except Exception as exc:
            self._receipts.fail(receipt_id, failure_code=getattr(exc, "code", "SEALED_COMPUTATION_FAILED"))
            raise
