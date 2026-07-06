"""Immutable promotion evidence bundles."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models.schemas_factor_promotion import EvidenceBundleDetail, PromotionGateEvaluation
from services.factor_discovery.evidence_paths import factor_discovery_paths
from services.factor_discovery.staging.extended_staging_artifact import ExtendedStagingArtifactStore

EVIDENCE_SCHEMA = "factor_promotion_evidence_v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _canonical_hash(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(body.encode()).hexdigest()}"


class FactorPromotionEvidenceService:
    def __init__(self, *, output_root: Path | None = None) -> None:
        self._root = output_root or factor_discovery_paths().promotion_evidence
        self._root.mkdir(parents=True, exist_ok=True)

    def build_bundle(
        self,
        *,
        candidate_id: str,
        factor_definition: dict[str, Any],
        diagnostics: dict[str, Any],
        gate_evaluation: PromotionGateEvaluation,
        staging_report: dict | None = None,
        sleeve_results: list[dict] | None = None,
        llm_summary: str | None = None,
    ) -> tuple[str, str, EvidenceBundleDetail]:
        staging = staging_report or {}
        manifest = staging.get("manifest") or {}
        bundle_id = f"fpev_{uuid.uuid4().hex[:12]}"
        generated_at = _utcnow()

        sleeve_cells = [
            c
            for c in staging.get("cell_results", [])
            if c.get("sleeve") == factor_definition.get("sleeve")
            and c.get("factor_id") == factor_definition.get("factor_id")
        ]
        baseline_cells = [
            c
            for c in staging.get("cell_results", [])
            if c.get("sleeve") == factor_definition.get("sleeve") and c.get("factor_role") == "baseline"
        ]

        body = {
            "schema_version": EVIDENCE_SCHEMA,
            "bundle_id": bundle_id,
            "candidate_id": candidate_id,
            "generated_at": generated_at.isoformat(),
            "factor_definition": factor_definition,
            "staging_manifest": manifest,
            "experiment_runs": [
                {"run_id": c.get("run_id"), "cell_id": c.get("cell_id"), "slice_id": c.get("slice_id")}
                for c in sleeve_cells
            ],
            "baseline_comparison": {
                "candidate_cells": len(sleeve_cells),
                "baseline_cells": len(baseline_cells),
                "candidate_acceptance": [c.get("acceptance_status") for c in sleeve_cells],
                "baseline_acceptance": [c.get("acceptance_status") for c in baseline_cells],
            },
            "regime_results": staging.get("slices") or [],
            "sleeve_results": sleeve_results or sleeve_cells,
            "quantile_results": diagnostics.get("monotonicity") or {},
            "turnover_and_cost": {
                "turnover": diagnostics.get("turnover"),
                "transaction_cost_impact_bps": diagnostics.get("transaction_cost_impact_bps"),
            },
            "failure_modes": staging.get("promotion_readiness", {}).get("weak_factors") or [],
            "reproducibility": {
                "results": staging.get("reproducibility_results") or [],
                "status": staging.get("promotion_readiness", {}).get("status"),
            },
            "negative_controls": staging.get("negative_controls") or [],
            "gate_evaluation": gate_evaluation.model_dump(mode="json"),
            "source_artifact_hashes": {
                k: v
                for k, v in {
                    "staging_run_id": staging.get("staging_run_id") or manifest.get("staging_run_id"),
                    "formula_hash": diagnostics.get("formula_hash"),
                    "panel_hash": diagnostics.get("panel_hash"),
                }.items()
                if v is not None
            },
            "diagnostics": diagnostics,
            "llm_summary": llm_summary,
        }
        bundle_hash = _canonical_hash(body)
        body["bundle_hash"] = bundle_hash

        path = self._root / f"{bundle_id}.json"
        path.write_text(json.dumps(body, indent=2, sort_keys=True, default=str), encoding="utf-8")

        detail = EvidenceBundleDetail(
            bundle_id=bundle_id,
            candidate_id=candidate_id,
            bundle_hash=bundle_hash,
            schema_version=EVIDENCE_SCHEMA,
            generated_at=generated_at,
            summary=self._structured_summary(factor_definition, gate_evaluation, diagnostics),
            gate_evaluation=gate_evaluation,
            factor_definition=factor_definition,
            staging_manifest=manifest,
            experiment_runs=body["experiment_runs"],
            baseline_comparison=body["baseline_comparison"],
            regime_results=body["regime_results"],
            sleeve_results=body["sleeve_results"],
            quantile_results=body["quantile_results"],
            turnover_and_cost=body["turnover_and_cost"],
            failure_modes=body["failure_modes"],
            reproducibility=body["reproducibility"],
            negative_controls=body["negative_controls"],
            source_artifact_hashes=body["source_artifact_hashes"],
            llm_summary=llm_summary,
        )
        return bundle_id, bundle_hash, detail

    def load(self, bundle_id: str) -> EvidenceBundleDetail | None:
        path = self._root / f"{bundle_id}.json"
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        stored_hash = raw.get("bundle_hash")
        verify = _canonical_hash({k: v for k, v in raw.items() if k != "bundle_hash"})
        if stored_hash and stored_hash != verify:
            raise ValueError("evidence bundle integrity mismatch")
        gate = raw.get("gate_evaluation")
        return EvidenceBundleDetail(
            bundle_id=raw["bundle_id"],
            candidate_id=raw["candidate_id"],
            bundle_hash=stored_hash or verify,
            schema_version=raw.get("schema_version", EVIDENCE_SCHEMA),
            generated_at=datetime.fromisoformat(raw["generated_at"]),
            summary=self._structured_summary(
                raw.get("factor_definition", {}),
                PromotionGateEvaluation.model_validate(gate) if gate else None,
                raw.get("diagnostics", {}),
            ),
            gate_evaluation=PromotionGateEvaluation.model_validate(gate) if gate else None,
            factor_definition=raw.get("factor_definition", {}),
            staging_manifest=raw.get("staging_manifest", {}),
            experiment_runs=raw.get("experiment_runs", []),
            baseline_comparison=raw.get("baseline_comparison", {}),
            regime_results=raw.get("regime_results", []),
            sleeve_results=raw.get("sleeve_results", []),
            quantile_results=raw.get("quantile_results", {}),
            turnover_and_cost=raw.get("turnover_and_cost", {}),
            failure_modes=raw.get("failure_modes", []),
            reproducibility=raw.get("reproducibility", {}),
            negative_controls=raw.get("negative_controls", []),
            source_artifact_hashes=raw.get("source_artifact_hashes", {}),
            llm_summary=raw.get("llm_summary"),
        )

    @staticmethod
    def _structured_summary(
        factor: dict,
        gate: PromotionGateEvaluation | None,
        diagnostics: dict,
    ) -> str:
        name = factor.get("display_name") or factor.get("factor_id")
        sleeve = factor.get("sleeve", "unknown")
        acceptance = diagnostics.get("acceptance_status", "unknown")
        gate_status = "pass" if gate and gate.overall_pass else "fail" if gate else "unknown"
        blocking = gate.blocking_failures if gate else []
        return (
            f"Promotion evidence for {name} ({sleeve}). "
            f"Staging acceptance: {acceptance}. Gate evaluation: {gate_status}. "
            f"Blocking failures: {blocking or 'none'}. "
            "Advisory only — does not affect live ranking."
        )

    def load_staging_report(self, staging_run_id: str | None) -> dict | None:
        if not staging_run_id:
            return ExtendedStagingArtifactStore().latest()
        store = ExtendedStagingArtifactStore()
        path = store._root / f"extended_staging_{staging_run_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        latest = store.latest()
        if latest and latest.get("staging_run_id") == staging_run_id:
            return latest
        return None
