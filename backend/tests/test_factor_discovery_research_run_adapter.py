"""Research Results adapter tests for Factor Discovery."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.repositories import FactorDiscoveryRunRepository
from services.factor_discovery.research_run_adapter import adapter_factor_discovery


def test_failed_run_summary_without_artifact(isolated_backend_env):
    run_id = FactorDiscoveryRunRepository().create(
        factor_id="fail_factor",
        factor_version="1.0.0",
        research_family_id="ffam_fail",
        status="failed",
        error_code="COMPILE_FAILURE",
        error_summary="compile failed",
        created_by="test",
    )
    summary = adapter_factor_discovery(run_id)
    assert summary is not None
    assert summary.status == "failed"
    assert summary.verdict == "failed"
    assert "COMPILE_FAILURE" in summary.blockers
    assert summary.parameters["factor_id"] == "fail_factor"
