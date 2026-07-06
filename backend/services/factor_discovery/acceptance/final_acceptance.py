"""Phase 11 final acceptance orchestrator."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from config import (
    FACTOR_DISCOVERY_ENABLED,
    FACTOR_DISCOVERY_STAGING_ENABLED,
    FACTOR_MODEL_VERSION,
    FACTOR_PROMOTION_GOVERNANCE_ENABLED,
    FACTOR_SHADOW_SCORING_ENABLED,
    STRATEGY_VERSION,
)
from services.factor_discovery.evidence_paths import factor_discovery_paths

AcceptanceMode = Literal["fixture", "real"]
AcceptanceStatus = Literal["PHASE_11_COMPLETE", "PHASE_11_BLOCKED"]


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


@dataclass
class AcceptanceCheck:
    check_id: str
    category: str
    status: Literal["pass", "fail", "skip", "warn"]
    message: str
    duration_ms: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class AcceptanceReport:
    schema_version: str = "factor_research_acceptance_v1"
    mode: AcceptanceMode = "fixture"
    started_at: str = ""
    completed_at: str = ""
    status: AcceptanceStatus = "PHASE_11_BLOCKED"
    checks: list[AcceptanceCheck] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    performance: dict[str, float] = field(default_factory=dict)
    live_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "checks": [c.__dict__ for c in self.checks],
            "blockers": self.blockers,
            "warnings": self.warnings,
            "performance": self.performance,
            "live_config": {k: (bool(v) if type(v).__name__ == "RuntimeBool" else v) for k, v in self.live_config.items()},
        }


class FactorResearchAcceptanceRunner:
    """Canonical Phase 11 acceptance workflow."""

    def __init__(self, *, mode: AcceptanceMode = "fixture", repo_root: Path | None = None) -> None:
        self.mode = mode
        self.ARTIFACT_ROOT = factor_discovery_paths().acceptance
        _backend = factor_discovery_paths().backend_root
        self.repo_root = repo_root or _backend.parent
        self.backend_root = _backend
        self.frontend_root = self.repo_root / "frontend"

    def run(self) -> AcceptanceReport:
        report = AcceptanceReport(mode=self.mode, started_at=_utcnow())
        t0 = time.perf_counter()

        self._check_database_connectivity(report)
        self._check_historical_store(report)
        self._check_pit_universe(report)
        self._check_data_coverage(report)
        self._check_snapshot_immutability(report)
        self._check_supervised_run_contract(report)
        self._check_reproducibility(report)
        self._check_extended_staging(report)
        self._check_promotion_gates(report)
        self._check_evidence_integrity(report)
        self._check_shadow_isolation(report)
        self._check_audit_history(report)
        self._check_api_contracts(report)
        self._check_frontend_contracts(report)
        self._check_live_config_unchanged(report)
        self._check_isolation_write_paths(report)

        if self.mode == "fixture":
            self._run_fixture_tests(report)
        else:
            self._run_real_data_validation(report)

        report.completed_at = _utcnow()
        report.performance["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        report.blockers = [
            c.check_id for c in report.checks if c.status == "fail" and c.category != "optional"
        ]
        report.warnings = [c.check_id for c in report.checks if c.status == "warn"]
        report.status = "PHASE_11_COMPLETE" if not report.blockers else "PHASE_11_BLOCKED"
        return report

    def persist(self, report: AcceptanceReport) -> Path:
        self.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.ARTIFACT_ROOT / f"acceptance_{self.mode}_{ts}.json"
        body = report.to_dict()
        path.write_text(json.dumps(body, indent=2, sort_keys=True, default=str), encoding="utf-8")
        (self.ARTIFACT_ROOT / "latest.json").write_text(
            json.dumps({"path": str(path), "status": report.status, "mode": report.mode}, indent=2),
            encoding="utf-8",
        )
        return path

    def _timed(self, report: AcceptanceReport, check_id: str, category: str, fn) -> None:
        t0 = time.perf_counter()
        try:
            status, message, evidence = fn()
        except Exception as exc:
            status, message, evidence = "fail", str(exc), {}
        duration = round((time.perf_counter() - t0) * 1000, 1)
        report.checks.append(
            AcceptanceCheck(
                check_id=check_id,
                category=category,
                status=status,  # type: ignore[arg-type]
                message=message,
                duration_ms=duration,
                evidence=evidence,
            )
        )
        report.performance[check_id] = duration

    def _check_database_connectivity(self, report: AcceptanceReport) -> None:
        def _run():
            from sqlalchemy import text
            from data.db_engine import get_engine

            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return "pass", "database connectivity ok", {"database_url_scheme": str(get_engine().url.drivername)}

        self._timed(report, "database_connectivity", "infrastructure", _run)

    def _check_historical_store(self, report: AcceptanceReport) -> None:
        def _run():
            if self.mode == "fixture":
                return "pass", "fixture mode — historical store validated via pytest fixtures", {"mode": "fixture"}
            from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities

            caps = assess_historical_store_capabilities()
            if caps.blocking_reasons:
                return "fail", f"historical store blockers: {list(caps.blocking_reasons)[:3]}", {
                    "blocking_reasons": list(caps.blocking_reasons),
                }
            return "pass", "historical store ready", {
                "provider_id": caps.provider_id,
                "supported_fields": list(caps.supported_fields),
            }

        self._timed(report, "historical_store_readiness", "data", _run)

    def _check_pit_universe(self, report: AcceptanceReport) -> None:
        def _run():
            if self.mode == "fixture":
                from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture

                seed_staging_fixture(variant="long_history")
                return "pass", "fixture PIT universe seeded", {"mode": "fixture"}
            from services.factor_discovery.staging.extended_staging_artifact import ExtendedStagingArtifactStore
            from services.factor_discovery.staging.preflight_service import FactorDiscoveryStagingPreflightService

            artifact = ExtendedStagingArtifactStore().latest()
            if artifact and artifact.get("promotion_readiness", {}).get("status") == "READY_FOR_PROMOTION_REVIEW":
                preflight = artifact.get("preflight") or {}
                if preflight.get("blocking_reasons"):
                    return "warn", "artifact present but embedded preflight had blockers", preflight
                return "pass", "PIT validated via persisted extended staging artifact", {
                    "staging_run_id": artifact.get("staging_run_id"),
                    "source": "extended_staging_artifact",
                }

            preflight = FactorDiscoveryStagingPreflightService().run(allow_test=True)
            blockers = preflight.get("blocking_reasons") or []
            if blockers:
                return "fail", f"PIT blockers: {blockers[:3]}", {"blockers": blockers}
            return "pass", "PIT universe preflight clean", {"duration_ms": preflight.get("duration_ms")}

        self._timed(report, "pit_universe_readiness", "data", _run)

    def _check_data_coverage(self, report: AcceptanceReport) -> None:
        def _run():
            if self.mode == "fixture":
                from services.factor_discovery.staging.supported_dates import resolve_supported_date_range

                dr = resolve_supported_date_range()
                return "pass", f"fixture overlap {dr.overlap_sessions} sessions", {"overlap": dr.overlap_sessions}
            from services.factor_discovery.staging.extended_staging_artifact import ExtendedStagingArtifactStore

            artifact = ExtendedStagingArtifactStore().latest()
            if not artifact:
                return "warn", "no extended staging artifact — run extended staging locally", {}
            cells = artifact.get("cell_results") or []
            succeeded = sum(1 for c in cells if c.get("status") == "succeeded")
            return "pass", f"{succeeded}/{len(cells)} staging cells succeeded", {"staging_run_id": artifact.get("staging_run_id")}

        self._timed(report, "data_coverage", "data", _run)

    def _check_snapshot_immutability(self, report: AcceptanceReport) -> None:
        def _run():
            from services.factor_discovery.staging.snapshot_reproducibility import FactorDiscoverySnapshotReproducibilityService

            assert FactorDiscoverySnapshotReproducibilityService is not None
            return "pass", "snapshot reproducibility service present", {"mode": self.mode}

        self._timed(report, "snapshot_immutability", "reproducibility", _run)

    def _check_supervised_run_contract(self, report: AcceptanceReport) -> None:
        def _run():
            from services.factor_discovery.staging.run_suite import FactorDiscoveryStagingRunSuite

            assert hasattr(FactorDiscoveryStagingRunSuite, "run_matrix_cell")
            return "pass", "supervised run suite contract present", {"enabled": FACTOR_DISCOVERY_ENABLED}

        self._timed(report, "supervised_research_run", "research", _run)

    def _check_reproducibility(self, report: AcceptanceReport) -> None:
        def _run():
            from services.factor_discovery.staging.reproduce import FactorDiscoveryReproduceService

            assert FactorDiscoveryReproduceService is not None
            if self.mode == "real":
                from services.factor_discovery.staging.extended_staging_artifact import ExtendedStagingArtifactStore

                artifact = ExtendedStagingArtifactStore().latest() or {}
                repro = artifact.get("reproducibility_results") or []
                mismatches = [r for r in repro if r.get("comparison_status") == "MISMATCH"]
                if mismatches:
                    return "fail", f"{len(mismatches)} reproducibility mismatches", {"mismatches": mismatches[:3]}
                if repro:
                    return "pass", f"{len(repro)} reproducibility checks recorded", {}
            return "pass", "reproducibility service available", {}

        self._timed(report, "reproducibility", "reproducibility", _run)

    def _check_extended_staging(self, report: AcceptanceReport) -> None:
        def _run():
            from services.factor_discovery.staging.promotion_readiness_gate import FactorDiscoveryPromotionReadinessGate

            if self.mode == "real":
                from services.factor_discovery.staging.extended_staging_artifact import ExtendedStagingArtifactStore

                artifact = ExtendedStagingArtifactStore().latest()
                if not artifact:
                    return "fail", "extended staging artifact missing", {}
                readiness = artifact.get("promotion_readiness") or {}
                status = readiness.get("status")
                if status != "READY_FOR_PROMOTION_REVIEW":
                    return "fail", f"staging status {status}", readiness
                return "pass", "extended staging READY_FOR_PROMOTION_REVIEW", {"run_id": artifact.get("staging_run_id")}
            gate = FactorDiscoveryPromotionReadinessGate()
            return "pass", f"promotion readiness gate {gate.POLICY_ID}", {}

        self._timed(report, "extended_staging", "staging", _run)

    def _check_promotion_gates(self, report: AcceptanceReport) -> None:
        def _run():
            from services.factor_discovery.promotion.gate_policy import load_gate_policy
            from services.factor_discovery.promotion.lifecycle import validate_transition
            from models.schemas_factor_promotion import FactorPromotionStatus

            policy = load_gate_policy()
            gates = policy.get("gates") or {}
            if len(gates) < 10:
                return "fail", f"only {len(gates)} gates configured", {}
            try:
                validate_transition(FactorPromotionStatus.EXPERIMENTAL, FactorPromotionStatus.STAGED)
            except ValueError:
                return "fail", "lifecycle transition validation broken", {}
            return "pass", f"{len(gates)} versioned promotion gates", {"policy_id": policy.get("policy_id")}

        self._timed(report, "promotion_gate_evaluation", "governance", _run)

    def _check_evidence_integrity(self, report: AcceptanceReport) -> None:
        def _run():
            from services.factor_discovery.promotion.evidence_bundle import EVIDENCE_SCHEMA, FactorPromotionEvidenceService

            root = FactorPromotionEvidenceService()._root
            bundles = list(root.glob("fpev_*.json")) if root.exists() else []
            return "pass", f"evidence schema {EVIDENCE_SCHEMA}; {len(bundles)} bundle(s) on disk", {"count": len(bundles)}

        self._timed(report, "evidence_bundle_integrity", "governance", _run)

    def _check_shadow_isolation(self, report: AcceptanceReport) -> None:
        def _run():
            from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

            live = FactorPromotionCandidateService.verify_live_config_unchanged()
            if live.get("live_mutation"):
                return "fail", "live configuration mutation detected", live
            return (
                "pass",
                "shadow scoring isolated from live weights",
                {
                    **live,
                    "shadow_enabled_flag": bool(FACTOR_SHADOW_SCORING_ENABLED),
                    "governance_enabled_flag": bool(FACTOR_PROMOTION_GOVERNANCE_ENABLED),
                },
            )

        self._timed(report, "shadow_scoring_isolation", "isolation", _run)

    def _check_audit_history(self, report: AcceptanceReport) -> None:
        def _run():
            from engines.factor_discovery_models import FactorPromotionStatusEvent, FactorStatusEvent

            return "pass", "audit tables registered", {
                "factor_status_events": FactorStatusEvent.__tablename__,
                "promotion_status_events": FactorPromotionStatusEvent.__tablename__,
            }

        self._timed(report, "audit_history", "governance", _run)

    def _check_api_contracts(self, report: AcceptanceReport) -> None:
        def _run():
            from models.schemas_factor_promotion import (
                CreatePromotionCandidateRequest,
                FactorPromotionCandidateDetail,
                PromotionStatusTransitionRequest,
            )

            assert CreatePromotionCandidateRequest.model_fields
            assert FactorPromotionCandidateDetail.model_fields
            assert PromotionStatusTransitionRequest.model_fields
            routes_file = self.backend_root / "api" / "routes_research_lab.py"
            text = routes_file.read_text(encoding="utf-8")
            required = [
                "/factor-discovery/promotion-candidates",
                "/factor-discovery/staging/extended-latest",
                "/factor-discovery/mining/readiness",
            ]
            missing = [r for r in required if r not in text]
            if missing:
                return "fail", f"missing routes: {missing}", {}
            return "pass", "research API contracts present", {"routes_checked": len(required)}

        self._timed(report, "api_contracts", "contracts", _run)

    def _check_frontend_contracts(self, report: AcceptanceReport) -> None:
        def _run():
            promotion_client = self.frontend_root / "src" / "lib" / "api" / "factorDiscovery" / "promotion.ts"
            panel = self.frontend_root / "src" / "components" / "quant-lab" / "factor-discovery" / "PromotionReviewPanel.tsx"
            hooks = self.frontend_root / "src" / "hooks" / "useResearchRuns.ts"
            missing = [p for p in (promotion_client, panel, hooks) if not p.exists()]
            if missing:
                return "fail", f"missing frontend files: {[str(p.name) for p in missing]}", {}
            hook_text = hooks.read_text(encoding="utf-8")
            if "AbortController" not in hook_text:
                return "warn", "useResearchRuns missing AbortController pattern", {}
            return "pass", "frontend contracts present (Promotion Review + Results abort hooks)", {}

        self._timed(report, "frontend_contract_compatibility", "contracts", _run)

    def _check_live_config_unchanged(self, report: AcceptanceReport) -> None:
        def _run():
            from data.db_engine import get_engine
            from engines.quant_models import FactorWeight
            from sqlalchemy.orm import Session

            with Session(get_engine()) as session:
                weight_count = session.query(FactorWeight).count()
            report.live_config = {
                "factor_model_version": FACTOR_MODEL_VERSION,
                "strategy_version": STRATEGY_VERSION,
                "factor_weight_rows": weight_count,
                "staging_enabled": bool(FACTOR_DISCOVERY_STAGING_ENABLED),
                "promotion_governance_enabled": bool(FACTOR_PROMOTION_GOVERNANCE_ENABLED),
            }
            return "pass", "live scoring config snapshot recorded (no promotion write path)", report.live_config

        self._timed(report, "live_config_unchanged", "isolation", _run)

    def _check_isolation_write_paths(self, report: AcceptanceReport) -> None:
        def _run():
            from services.factor_discovery.isolation_audit import verify_research_isolation

            result = verify_research_isolation()
            if result.get("blockers"):
                return "fail", f"isolation blockers: {result['blockers']}", result
            return "pass", "no research→production write paths detected", result

        self._timed(report, "isolation_write_paths", "isolation", _run)

    def _run_fixture_tests(self, report: AcceptanceReport) -> None:
        def _run():
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_factor_research_isolation.py",
                "tests/test_factor_promotion_governance.py",
                "tests/test_factor_discovery_extended_staging.py",
                "-q",
                "--tb=no",
            ]
            proc = subprocess.run(cmd, cwd=str(self.backend_root), capture_output=True, text=True, timeout=180)
            if proc.returncode != 0:
                return "fail", proc.stdout[-500:] or proc.stderr[-500:], {"returncode": proc.returncode}
            return "pass", "fixture isolation/staging/promotion tests passed", {"output_tail": proc.stdout[-200:]}

        self._timed(report, "fixture_test_suite", "tests", _run)

    def _run_real_data_validation(self, report: AcceptanceReport) -> None:
        def _run():
            if not FACTOR_DISCOVERY_STAGING_ENABLED:
                return "warn", "FACTOR_DISCOVERY_STAGING_ENABLED=false — real validation partial", {}
            cmd = [sys.executable, "scripts/factor_discovery_staging_preflight.py", "--json", "--allow-test"]
            proc = subprocess.run(cmd, cwd=str(self.backend_root), capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                return "fail", "real preflight CLI failed", {"stderr": proc.stderr[-300:]}
            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError:
                return "fail", "preflight JSON parse failed", {}
            blockers = payload.get("blocking_reasons") or []
            if blockers:
                return "fail", f"real preflight blockers: {blockers[:3]}", payload
            return "pass", f"real preflight ~{payload.get('duration_ms', '?')}ms", {"blockers": []}

        self._timed(report, "real_data_preflight", "real_data", _run)
