"""Staging acceptance gate."""
from __future__ import annotations

from services.factor_discovery.staging.policies import STAGING_READINESS_POLICY_ID


class FactorDiscoveryStagingAcceptanceGate:
    POLICY_ID = STAGING_READINESS_POLICY_ID

    def evaluate(
        self,
        *,
        preflight: dict,
        reproducibility_status: str | None = None,
        repository_tests_passed: bool = True,
        frontend_tests_passed: bool = True,
        typecheck_passed: bool = True,
        build_passed: bool = True,
        factor_discovery_lint_clean: bool = True,
    ) -> dict:
        blocking = list(preflight.get("blocking_reasons") or [])
        limitations: list[str] = []

        if not repository_tests_passed:
            blocking.append("repository_tests_failed")
        if not frontend_tests_passed:
            blocking.append("frontend_tests_failed")
        if not typecheck_passed:
            blocking.append("frontend_typecheck_failed")
        if not build_passed:
            blocking.append("frontend_build_failed")
        if not factor_discovery_lint_clean:
            limitations.append("factor_discovery_frontend_lint_not_clean")
        if reproducibility_status == "MISMATCH":
            blocking.append("reproducibility_mismatch")
        if reproducibility_status is None:
            limitations.append("reproducibility_not_executed")

        status = "NOT_READY"
        if not blocking:
            status = "READY_WITH_LIMITATIONS" if limitations else "READY_FOR_EXTENDED_STAGING"

        return {
            "policy_id": self.POLICY_ID,
            "status": status,
            "blocking_findings": blocking,
            "limitations": limitations,
            "no_production_scan": True,
            "no_sealed_access": True,
        }
