"""Extended real-data staging runner for Phase 9B.2."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import config as app_config
from services.factor_discovery.evidence_paths import factor_discovery_paths
from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities
from services.factor_discovery.snapshot_service import FactorResearchSnapshotService
from services.factor_discovery.staging.diagnostics_extractor import load_diagnostics_for_run
from services.factor_discovery.staging.extended_staging_artifact import ExtendedStagingArtifactStore
from services.factor_discovery.staging.import_config import require_staging_mutations_enabled
from services.factor_discovery.staging.negative_controls import ExtendedStagingNegativeControls
from services.factor_discovery.staging.preflight_service import FactorDiscoveryStagingPreflightService
from services.factor_discovery.staging.promotion_readiness_gate import FactorDiscoveryPromotionReadinessGate
from services.factor_discovery.staging.reproduce import FactorDiscoveryReproduceService
from services.factor_discovery.staging.run_suite import FactorDiscoveryStagingRunSuite
from services.factor_discovery.staging.staging_manifest import build_extended_staging_manifest
from services.factor_discovery.staging.staging_matrix import STAGING_MATRIX_FACTORS, build_staging_matrix
from services.factor_discovery.staging.supported_dates import resolve_supported_date_range


class FactorMiningExtendedStagingRunner:
    """Canonical orchestrator for extended staging matrix validation."""

    def __init__(self, *, output_dir: Path | None = None) -> None:
        self._suite = FactorDiscoveryStagingRunSuite()
        self._store = ExtendedStagingArtifactStore(
            output_root=output_dir or factor_discovery_paths().extended_staging
        )
        self._snapshot_cache: dict[str, dict] = {}

    def run(
        self,
        *,
        sleeves: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        random_seed: int = 42,
        actor: str = "extended-staging",
        dry_run: bool = False,
    ) -> dict:
        require_staging_mutations_enabled()
        t_total = time.perf_counter()
        staging_run_id = f"extstage_{uuid.uuid4().hex[:12]}"
        runtime: dict = {}

        t0 = time.perf_counter()
        preflight = FactorDiscoveryStagingPreflightService().run()
        runtime["preflight_ms"] = int((time.perf_counter() - t0) * 1000)
        preflight_blockers = list(preflight.get("blocking_reasons") or [])

        date_range = resolve_supported_date_range(requested_start=start_date, requested_end=end_date)
        if not date_range.supported_start or not date_range.supported_end:
            return self._finalize_blocked(
                staging_run_id=staging_run_id,
                blockers=["insufficient_supported_date_overlap"],
                preflight=preflight,
                date_range=date_range.to_dict(),
                runtime=runtime,
            )

        resolved_start = date_range.supported_start
        resolved_end = date_range.supported_end
        matrix = build_staging_matrix(
            sleeves=sleeves,
            slices=date_range.slices,
            random_seed=random_seed,
        )
        caps = assess_historical_store_capabilities()
        manifest = build_extended_staging_manifest(
            staging_run_id=staging_run_id,
            sleeves=matrix.sleeves,
            start_date=resolved_start,
            end_date=resolved_end,
            pit_universe_version=caps.provider_data_version,
            matrix_spec=matrix.to_dict(),
            random_seed=random_seed,
        )

        if dry_run:
            return {
                "staging_run_id": staging_run_id,
                "dry_run": True,
                "manifest": manifest.to_dict(),
                "date_range": date_range.to_dict(),
                "matrix": matrix.to_dict(),
                "preflight_blockers": preflight_blockers,
            }

        negative_controls: list[dict] = []
        cell_results: list[dict] = []
        reproducibility_results: list[dict] = []
        snapshots_reused = 0
        snapshots_built = 0

        t0 = time.perf_counter()
        reference_snap = self._get_or_materialize_snapshot(resolved_start, resolved_end)
        runtime["reference_snapshot_ms"] = int((time.perf_counter() - t0) * 1000)
        if reference_snap.get("blocking_codes"):
            return self._finalize_blocked(
                staging_run_id=staging_run_id,
                blockers=list(reference_snap["blocking_codes"]),
                preflight=preflight,
                manifest=manifest.to_dict(),
                date_range=date_range.to_dict(),
                runtime=runtime,
            )
        snapshots_built += 1

        panel = FactorResearchSnapshotService().load_verified(reference_snap["snapshot_id"])
        cut_date = resolved_start
        negative_controls = [
            r.to_dict() for r in ExtendedStagingNegativeControls().run_all(panel, cut_date=cut_date)
        ]

        factor_specs = {f["factor_key"]: f for f in STAGING_MATRIX_FACTORS}
        repro_candidates: list[dict] = []

        for cell in matrix.cells:
            cache_key = f"{cell.start_date}:{cell.end_date}"
            if cache_key in self._snapshot_cache:
                snap = self._snapshot_cache[cache_key]
                snapshots_reused += 1
            else:
                t0 = time.perf_counter()
                snap = self._suite.materialize_snapshot(
                    start_session=cell.start_date,
                    end_session=cell.end_date,
                )
                runtime.setdefault("snapshot_ms_by_slice", {})[cell.slice_id] = int((time.perf_counter() - t0) * 1000)
                if snap.get("blocking_codes"):
                    cell_results.append(
                        {
                            "cell_id": cell.cell_id,
                            "status": "blocked",
                            "blocking_codes": snap["blocking_codes"],
                            "sleeve": cell.sleeve,
                            "factor_key": cell.factor_key,
                        }
                    )
                    continue
                self._snapshot_cache[cache_key] = snap
                snapshots_built += 1
                snap = self._snapshot_cache[cache_key]

            spec = factor_specs[cell.factor_key]
            spec_payload = {
                "factor_key": spec["factor_key"],
                "display_name": spec["display_name"],
                "dsl": spec["dsl"],
                "actor": actor,
            }
            t0 = time.perf_counter()
            run_result = self._suite.run_matrix_cell(
                snapshot_id=snap["snapshot_id"],
                factor_spec=spec_payload,
                sleeve=cell.sleeve,
                slice_start=cell.start_date,
                slice_end=cell.end_date,
                idempotency_key=f"{staging_run_id}:{cell.cell_id}",
                created_by=actor,
            )
            eval_ms = int((time.perf_counter() - t0) * 1000)
            cell_record = {
                "cell_id": cell.cell_id,
                "sleeve": cell.sleeve,
                "slice_id": cell.slice_id,
                "factor_key": cell.factor_key,
                "factor_role": cell.factor_role,
                "snapshot_id": snap["snapshot_id"],
                "coverage": snap.get("coverage"),
                "status": run_result.get("status", "failed"),
                "run_id": run_result.get("run_id"),
                "artifact_id": run_result.get("artifact_id"),
                "acceptance_status": run_result.get("acceptance_status"),
                "duration_ms": run_result.get("duration_ms", eval_ms),
                "error": run_result.get("error"),
            }
            if run_result.get("run_id"):
                try:
                    cell_record["diagnostics"] = load_diagnostics_for_run(
                        str(run_result["run_id"]),
                        sleeve=cell.sleeve,
                        slice_id=cell.slice_id,
                    )
                except Exception as exc:
                    cell_record["diagnostics_error"] = str(exc)[:200]
            cell_results.append(cell_record)
            if cell.reproducibility_candidate and run_result.get("run_id"):
                repro_candidates.append({**cell_record, "cell": cell.to_dict()})

        for cand in repro_candidates[:4]:
            repeat = self._suite.run_matrix_cell(
                snapshot_id=cand["snapshot_id"],
                factor_spec={
                    "factor_key": cand["factor_key"],
                    "display_name": cand["factor_key"],
                    "dsl": factor_specs[cand["factor_key"]]["dsl"],
                    "actor": actor,
                },
                sleeve=cand["sleeve"],
                slice_start=cand["cell"]["start_date"],
                slice_end=cand["cell"]["end_date"],
                idempotency_key=f"{staging_run_id}:repro:{cand['cell_id']}:{uuid.uuid4().hex[:6]}",
                created_by=actor,
            )
            if cand.get("run_id") and repeat.get("run_id"):
                comparison = FactorDiscoveryReproduceService().verify_run(
                    str(cand["run_id"]),
                    compare_run_id=str(repeat["run_id"]),
                ).to_dict()
                comparison["cell_id"] = cand["cell_id"]
                reproducibility_results.append(comparison)

        runtime["total_ms"] = int((time.perf_counter() - t_total) * 1000)
        runtime["snapshots_reused"] = snapshots_reused
        runtime["snapshots_built"] = snapshots_built
        runtime["cells_executed"] = len(cell_results)

        promotion = FactorDiscoveryPromotionReadinessGate().evaluate(
            preflight_blockers=preflight_blockers,
            sleeves_tested=matrix.sleeves,
            negative_controls=negative_controls,
            reproducibility_results=reproducibility_results,
            cell_results=cell_results,
            runtime=runtime,
            live_config_mutated=False,
        )

        report = {
            "staging_run_id": staging_run_id,
            "manifest": manifest.to_dict(),
            "date_range": date_range.to_dict(),
            "matrix": matrix.to_dict(),
            "preflight": {"blocking_reasons": preflight_blockers},
            "negative_controls": negative_controls,
            "cell_results": cell_results,
            "reproducibility_results": reproducibility_results,
            "runtime": runtime,
            "promotion_readiness": promotion,
        }
        path = self._store.persist(report)
        report["artifact_path"] = str(path)
        return report

    def _get_or_materialize_snapshot(self, start: str, end: str) -> dict:
        key = f"{start}:{end}"
        if key not in self._snapshot_cache:
            self._snapshot_cache[key] = self._suite.materialize_snapshot(start_session=start, end_session=end)
        return self._snapshot_cache[key]

    def _finalize_blocked(
        self,
        *,
        staging_run_id: str,
        blockers: list[str],
        preflight: dict,
        date_range: dict | None = None,
        manifest: dict | None = None,
        runtime: dict | None = None,
    ) -> dict:
        promotion = FactorDiscoveryPromotionReadinessGate().evaluate(
            preflight_blockers=blockers,
            sleeves_tested=[],
            negative_controls=[],
            reproducibility_results=[],
            cell_results=[],
            runtime=runtime or {},
        )
        report = {
            "staging_run_id": staging_run_id,
            "manifest": manifest,
            "date_range": date_range,
            "preflight": preflight,
            "promotion_readiness": promotion,
            "blocking_reasons": blockers,
        }
        path = self._store.persist(report)
        report["artifact_path"] = str(path)
        return report
