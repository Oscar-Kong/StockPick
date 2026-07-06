"""Staging research run orchestration."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

import config as app_config
from engines.factor.discovery.formatter import format_factor_expression
from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit, FactorDefinition, FactorDirection, FactorLifecycleStatus
from services.factor_discovery.data_provider import get_runtime_factor_research_provider
from services.factor_discovery.experiment_runner import FactorDiscoveryExperimentRunner, FactorDiscoveryRunRequest
from services.factor_discovery.historical_store_provider import HISTORICAL_STORE_PROVIDER_ID, RESEARCH_POLICY_ID
from services.factor_discovery.repositories import FactorDefinitionRepository, FactorResearchFamilyRepository
from services.factor_discovery.snapshot_service import FactorResearchSnapshotService, SnapshotRequest
from services.factor_discovery.staging.coverage_audit import FactorDiscoveryCoverageAuditService
from services.factor_discovery.staging.policies import STAGING_FROZEN_FACTOR, STAGING_VALIDATION_CONFIG
from services.factor_discovery.staging.reproduce import FactorDiscoveryReproduceService
from services.factor_discovery.staging.snapshot_reproducibility import FactorDiscoverySnapshotReproducibilityService


def _period_split_for_slice(start_date: str, end_date: str) -> DiscoveryPeriodSplit:
    start = date.fromisoformat(start_date[:10])
    end = date.fromisoformat(end_date[:10])
    span = (end - start).days
    if span < 90:
        disc_end = start + timedelta(days=max(span // 3, 20))
        val_start = disc_end + timedelta(days=3)
        val_end = end - timedelta(days=30)
        sealed_start = val_end + timedelta(days=3)
        sealed_end = end
    else:
        disc_end = start + timedelta(days=span // 3)
        val_start = disc_end + timedelta(days=5)
        val_end = start + timedelta(days=(2 * span) // 3)
        sealed_start = val_end + timedelta(days=5)
        sealed_end = end
    if val_end <= val_start:
        val_start = disc_end + timedelta(days=1)
        val_end = end - timedelta(days=10)
    if sealed_end <= sealed_start:
        sealed_start = val_end + timedelta(days=1)
        sealed_end = end
    return DiscoveryPeriodSplit(
        discovery_start=start,
        discovery_end=disc_end,
        validation_start=val_start,
        validation_end=val_end,
        sealed_test_start=sealed_start,
        sealed_test_end=sealed_end,
        embargo_days=0,
        min_sealed_test_days=min(30, max(1, (sealed_end - sealed_start).days)),
    )


@dataclass
class StagingRunResult:
    factor_key: str
    snapshot_id: str
    panel_hash: str
    row_count: int
    symbol_count: int
    duration_ms: int
    blocking_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "factor_key": self.factor_key,
            "snapshot_id": self.snapshot_id,
            "panel_hash": self.panel_hash,
            "row_count": self.row_count,
            "symbol_count": self.symbol_count,
            "duration_ms": self.duration_ms,
            "blocking_codes": self.blocking_codes,
        }


class FactorDiscoveryStagingRunSuite:
    def __init__(self, *, storage_root=None) -> None:
        self._snapshot_svc = FactorResearchSnapshotService(storage_root=storage_root)
        self._repro = FactorDiscoverySnapshotReproducibilityService(storage_root=storage_root)

    def materialize_snapshot(
        self,
        *,
        start_session: str | None,
        end_session: str | None,
        required_fields: frozenset[str] | None = None,
    ) -> dict:
        if app_config.FACTOR_RESEARCH_DATA_PROVIDER != "historical_store":
            return {"blocking_codes": ["data_provider_not_historical_store"]}
        provider = get_runtime_factor_research_provider()
        from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities

        caps = assess_historical_store_capabilities()
        if caps.blocking_reasons:
            return {"blocking_codes": list(caps.blocking_reasons)}
        req = SnapshotRequest(
            provider_id=HISTORICAL_STORE_PROVIDER_ID,
            data_source_policy_id=RESEARCH_POLICY_ID,
            start_session=start_session,
            end_session=end_session,
            universe_source="universe_pit_v1",
            required_fields=required_fields or frozenset({"adjusted_close", "volume"}),
            provider_data_version=caps.provider_data_version,
        )
        t0 = time.perf_counter()
        try:
            snapshot_id, panel, ref = self._snapshot_svc.materialize(provider, req)
        except Exception as exc:
            from services.factor_discovery.errors import FactorDiscoveryError

            code = getattr(exc, "code", "SNAPSHOT_MATERIALIZE_FAILED")
            return {
                "blocking_codes": [str(code)],
                "error": str(exc)[:300],
                "duration_ms": int((time.perf_counter() - t0) * 1000),
            }
        repro = self._repro.verify_identical_request(provider, req)
        coverage = FactorDiscoveryCoverageAuditService().audit_panel(
            panel, required_fields=set(req.required_fields)
        )
        return {
            "snapshot_id": snapshot_id,
            "panel_hash": ref.panel_hash,
            "canonical_session_hash": ref.canonical_session_hash,
            "row_count": ref.row_count,
            "symbol_count": ref.symbol_count,
            "date_count": ref.date_count,
            "reproducibility": repro.to_dict(),
            "coverage": coverage.to_dict(),
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "validation_config": STAGING_VALIDATION_CONFIG,
        }

    def ensure_frozen_factor(self) -> dict:
        spec = STAGING_FROZEN_FACTOR
        ast = parse_factor_expression(spec["dsl"])
        definition = FactorDefinition(
            factor_id=spec["factor_key"],
            version="1.0.0",
            display_name=spec["display_name"],
            expression=ast,
            expected_direction=FactorDirection.HIGHER_IS_BETTER,
            intended_universe="research",
            rebalance_frequency="monthly",
            holding_period_sessions=21,
            required_fields=["return_126d"],
            data_source_policy_id=RESEARCH_POLICY_ID,
            lifecycle_status=FactorLifecycleStatus.COMPILED,
        )
        repo = FactorDefinitionRepository()
        existing = repo.get(definition.factor_id, definition.version)
        if existing is None:
            repo.create_version(
                definition,
                created_by=spec["actor"],
                canonical_dsl=format_factor_expression(ast),
                canonical_ast=definition.expression.model_dump(mode="json"),
            )
        return {
            "factor_id": definition.factor_id,
            "factor_version": definition.version,
            "formula": spec["dsl"],
            "actor": spec["actor"],
            "reason": spec["reason"],
        }

    def ensure_factor(self, spec: dict) -> dict:
        ast = parse_factor_expression(spec["dsl"])
        definition = FactorDefinition(
            factor_id=spec["factor_key"],
            version="1.0.0",
            display_name=spec["display_name"],
            expression=ast,
            expected_direction=FactorDirection.HIGHER_IS_BETTER,
            intended_universe=spec.get("intended_universe", "research"),
            rebalance_frequency="monthly",
            holding_period_sessions=21,
            data_source_policy_id=RESEARCH_POLICY_ID,
            lifecycle_status=FactorLifecycleStatus.COMPILED,
        )
        repo = FactorDefinitionRepository()
        if repo.get(definition.factor_id, definition.version) is None:
            repo.create_version(
                definition,
                created_by=spec.get("actor", "staging-operator"),
                canonical_dsl=format_factor_expression(ast),
                canonical_ast=definition.expression.model_dump(mode="json"),
            )
        return {
            "factor_id": definition.factor_id,
            "factor_version": definition.version,
            "formula": spec["dsl"],
        }

    def run_matrix_cell(
        self,
        *,
        snapshot_id: str,
        factor_spec: dict,
        sleeve: str,
        slice_start: str,
        slice_end: str,
        idempotency_key: str,
        created_by: str = "extended-staging",
    ) -> dict:
        if not app_config.FACTOR_DISCOVERY_ENABLED:
            return {"status": "blocked", "blocking_codes": ["factor_discovery_disabled"]}
        if app_config.FACTOR_RESEARCH_DATA_PROVIDER != "historical_store":
            return {"status": "blocked", "blocking_codes": ["data_provider_not_historical_store"]}

        factor = self.ensure_factor({**factor_spec, "intended_universe": sleeve})
        family_id = FactorResearchFamilyRepository().create(
            research_objective=f"Extended staging {sleeve} {factor_spec['factor_key']}",
            intended_universe=sleeve,
            primary_horizon_sessions=STAGING_VALIDATION_CONFIG["primary_horizon"],
            data_source_policy_id=RESEARCH_POLICY_ID,
            validation_config_family_id="staging_validation_config_v1",
            created_by=created_by,
        )
        period = _period_split_for_slice(slice_start, slice_end)
        vconfig = FactorValidationConfig(
            primary_horizon_sessions=STAGING_VALIDATION_CONFIG["primary_horizon"],
            outcome_horizons_sessions=tuple(STAGING_VALIDATION_CONFIG["outcome_horizons"]),
            one_way_cost_bps=STAGING_VALIDATION_CONFIG["transaction_cost_bps"],
            rebalance_every_sessions=21,
            min_discovery_sessions=10,
            min_validation_sessions=10,
            min_sealed_test_sessions=5,
            min_walk_forward_folds=1,
            declared_hypothesis_family_size=1,
        )
        runner = FactorDiscoveryExperimentRunner()
        t0 = time.perf_counter()
        try:
            result = runner.run(
                FactorDiscoveryRunRequest(
                    experiment_id=None,
                    job_id=None,
                    factor_id=factor["factor_id"],
                    factor_version=factor["factor_version"],
                    research_family_id=family_id,
                    period_split=period,
                    validation_config=vconfig,
                    created_by=created_by,
                    idempotency_key=idempotency_key,
                    snapshot_id=snapshot_id,
                )
            )
            status = "succeeded" if result.get("status") == "completed" else "failed"
            return {
                **result,
                "status": status,
                "factor": factor,
                "family_id": family_id,
                "snapshot_id": snapshot_id,
                "sleeve": sleeve,
                "duration_ms": int((time.perf_counter() - t0) * 1000),
            }
        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc)[:500],
                "factor": factor,
                "snapshot_id": snapshot_id,
                "sleeve": sleeve,
                "duration_ms": int((time.perf_counter() - t0) * 1000),
            }

    def run_supervised_experiment(
        self,
        *,
        snapshot_id: str,
        created_by: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        if not app_config.FACTOR_DISCOVERY_ENABLED:
            return {"blocking_codes": ["factor_discovery_disabled"]}
        if app_config.FACTOR_RESEARCH_DATA_PROVIDER != "historical_store":
            return {"blocking_codes": ["data_provider_not_historical_store"]}

        factor = self.ensure_frozen_factor()
        family_id = FactorResearchFamilyRepository().create(
            research_objective="Phase 9B.1 staging reproducibility",
            intended_universe="research",
            primary_horizon_sessions=STAGING_VALIDATION_CONFIG["primary_horizon"],
            data_source_policy_id=RESEARCH_POLICY_ID,
            validation_config_family_id="staging_validation_config_v1",
            created_by=created_by or factor["actor"],
        )
        period = DiscoveryPeriodSplit(
            discovery_start=date.fromisoformat(STAGING_VALIDATION_CONFIG["discovery_start"]),
            discovery_end=date.fromisoformat(STAGING_VALIDATION_CONFIG["discovery_end"]),
            validation_start=date.fromisoformat(STAGING_VALIDATION_CONFIG["validation_start"]),
            validation_end=date.fromisoformat(STAGING_VALIDATION_CONFIG["validation_end"]),
            sealed_test_start=date.fromisoformat(STAGING_VALIDATION_CONFIG["sealed_test_start"]),
            sealed_test_end=date.fromisoformat(STAGING_VALIDATION_CONFIG["sealed_test_end"]),
            embargo_days=STAGING_VALIDATION_CONFIG["embargo_sessions"],
            min_sealed_test_days=STAGING_VALIDATION_CONFIG["min_sealed_test_days"],
        )
        vconfig = FactorValidationConfig(
            primary_horizon_sessions=STAGING_VALIDATION_CONFIG["primary_horizon"],
            outcome_horizons_sessions=tuple(STAGING_VALIDATION_CONFIG["outcome_horizons"]),
            one_way_cost_bps=STAGING_VALIDATION_CONFIG["transaction_cost_bps"],
            rebalance_every_sessions=21,
            min_discovery_sessions=20,
            min_validation_sessions=20,
            min_sealed_test_sessions=10,
            declared_hypothesis_family_size=1,
        )
        runner = FactorDiscoveryExperimentRunner()
        t0 = time.perf_counter()
        result = runner.run(
            FactorDiscoveryRunRequest(
                experiment_id=None,
                job_id=None,
                factor_id=factor["factor_id"],
                factor_version=factor["factor_version"],
                research_family_id=family_id,
                period_split=period,
                validation_config=vconfig,
                created_by=created_by or factor["actor"],
                idempotency_key=idempotency_key,
                snapshot_id=snapshot_id,
            )
        )
        return {
            **result,
            "factor": factor,
            "family_id": family_id,
            "snapshot_id": snapshot_id,
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        }

    def compare_repeat_runs(self, run_id_a: str, run_id_b: str) -> dict:
        svc = FactorDiscoveryReproduceService()
        return svc.verify_run(run_id_a, compare_run_id=run_id_b).to_dict()

    def run_full_staging_pipeline(
        self,
        *,
        start_session: str,
        end_session: str,
        created_by: str | None = None,
    ) -> dict:
        snap = self.materialize_snapshot(start_session=start_session, end_session=end_session)
        if snap.get("blocking_codes"):
            return {"stage": "snapshot", **snap}
        snapshot_id = snap["snapshot_id"]
        run1 = self.run_supervised_experiment(
            snapshot_id=snapshot_id,
            created_by=created_by,
            idempotency_key=f"staging_run_{uuid.uuid4().hex[:8]}",
        )
        if run1.get("blocking_codes"):
            return {"stage": "run", "snapshot": snap, **run1}
        run2 = self.run_supervised_experiment(
            snapshot_id=snapshot_id,
            created_by=created_by,
            idempotency_key=f"staging_run_{uuid.uuid4().hex[:8]}",
        )
        comparison = self.compare_repeat_runs(str(run1["run_id"]), str(run2["run_id"]))
        repro_a = FactorDiscoveryReproduceService().verify_run(str(run1["run_id"]))
        return {
            "snapshot": snap,
            "first_run": run1,
            "repeat_run": run2,
            "repeat_comparison": comparison,
            "cross_process_verification": repro_a.to_dict(),
        }
