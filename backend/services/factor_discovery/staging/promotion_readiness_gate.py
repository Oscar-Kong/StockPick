"""Final promotion-readiness decision for Phase 9B.2."""
from __future__ import annotations

from services.factor_discovery.staging.policies import STAGING_COVERAGE_MINIMUMS

PROMOTION_READINESS_POLICY_ID = "factor_discovery_promotion_readiness_v1"


class FactorDiscoveryPromotionReadinessGate:
    POLICY_ID = PROMOTION_READINESS_POLICY_ID

    def evaluate(
        self,
        *,
        preflight_blockers: list[str],
        sleeves_tested: list[str],
        negative_controls: list[dict],
        reproducibility_results: list[dict],
        cell_results: list[dict],
        runtime: dict | None = None,
        live_config_mutated: bool = False,
    ) -> dict:
        blockers: list[str] = list(preflight_blockers)
        warnings: list[str] = []
        weak_factors: list[str] = []
        infra_failures: list[str] = []
        expected_control_failures: list[str] = []

        required_sleeves = {"penny", "compounder"}
        if not required_sleeves.issubset(set(sleeves_tested)):
            blockers.append("both_active_sleeves_not_tested")

        for ctrl in negative_controls:
            if ctrl.get("blocking") and not ctrl.get("passed"):
                blockers.append(f"negative_control_failed:{ctrl.get('control_id')}")
            elif not ctrl.get("passed") and not ctrl.get("blocking"):
                expected_control_failures.append(str(ctrl.get("control_id")))

        for repro in reproducibility_results:
            if repro.get("comparison_status") == "MISMATCH":
                blockers.append(f"reproducibility_mismatch:{repro.get('cell_id')}")
            elif repro.get("comparison_status") not in {
                "EXACT_MATCH",
                "SEMANTIC_MATCH_WITH_EXPECTED_CONTEXT_DIFFERENCE",
            }:
                warnings.append(f"repro_not_comparable:{repro.get('cell_id')}")

        min_symbols = STAGING_COVERAGE_MINIMUMS["min_eligible_symbols_per_date"]
        min_dates = STAGING_COVERAGE_MINIMUMS["min_valid_validation_dates"]
        for cell in cell_results:
            if cell.get("status") == "failed":
                infra_failures.append(cell.get("cell_id", "unknown"))
            if cell.get("status") == "blocked":
                blockers.append(f"cell_blocked:{cell.get('cell_id')}")
            coverage = cell.get("coverage") or {}
            sym = coverage.get("symbol_count") or 0
            dates = coverage.get("date_count") or 0
            if sym and sym < min_symbols:
                warnings.append(f"low_symbol_coverage:{cell.get('cell_id')}:{sym}")
            if dates and dates < min_dates:
                warnings.append(f"low_date_coverage:{cell.get('cell_id')}:{dates}")
            if cell.get("acceptance_status") == "FAIL" and cell.get("factor_role") == "candidate":
                weak_factors.append(cell.get("factor_key", cell.get("cell_id", "unknown")))

        if live_config_mutated:
            blockers.append("live_configuration_mutated")

        if infra_failures:
            blockers.append("infrastructure_failures_present")

        status = "READY_FOR_PROMOTION_REVIEW" if not blockers else "NOT_READY_FOR_PROMOTION_REVIEW"
        return {
            "policy_id": self.POLICY_ID,
            "status": status,
            "blocking_findings": list(dict.fromkeys(blockers)),
            "warnings": list(dict.fromkeys(warnings)),
            "weak_factors": list(dict.fromkeys(weak_factors)),
            "infrastructure_failures": infra_failures,
            "expected_negative_control_failures": expected_control_failures,
            "runtime": runtime or {},
            "no_production_scan_mutation": not live_config_mutated,
            "no_factor_promotion": True,
        }
