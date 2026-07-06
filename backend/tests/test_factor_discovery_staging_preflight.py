"""Staging preflight and acceptance tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from services.factor_discovery.staging.acceptance_gate import FactorDiscoveryStagingAcceptanceGate
from services.factor_discovery.staging.preflight_service import FactorDiscoveryStagingPreflightService
from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture


def test_preflight_blocks_empty_db(isolated_backend_env):
    report = FactorDiscoveryStagingPreflightService().run(allow_test=True)
    assert "no_daily_quotes" in report["price_readiness"]["blocking_codes"] or report["price_readiness"]["total_rows"] == 0
    assert report["read_only"] is True


def test_preflight_passes_with_valid_fixture(isolated_backend_env, monkeypatch, tmp_path):
    seed_staging_fixture(variant="valid")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "historical_store", raising=False)
    monkeypatch.setattr(config, "FACTOR_RESEARCH_SNAPSHOT_ROOT", str(tmp_path), raising=False)
    report = FactorDiscoveryStagingPreflightService().run(allow_test=True)
    assert report["price_readiness"]["adjusted_rows"] > 0
    assert report["universe_readiness"]["unique_dates"] >= 2
    assert "constant_membership_detected" not in report["universe_readiness"]["blocking_codes"]


def test_preflight_blocks_mixed_adjustment(isolated_backend_env):
    seed_staging_fixture(variant="mixed_adjustment")
    report = FactorDiscoveryStagingPreflightService().run(allow_test=True)
    assert "mixed_adjustment_within_symbol" in report["price_readiness"]["blocking_codes"]


def test_preflight_blocks_empty_universe(isolated_backend_env):
    seed_staging_fixture(variant="empty_universe")
    report = FactorDiscoveryStagingPreflightService().run(allow_test=True)
    assert "universe_pit_empty" in report["universe_readiness"]["blocking_codes"]


def test_acceptance_not_ready_on_blocking(isolated_backend_env):
    report = FactorDiscoveryStagingPreflightService().run(allow_test=True)
    acceptance = FactorDiscoveryStagingAcceptanceGate().evaluate(preflight=report)
    assert acceptance["status"] == "NOT_READY"
    assert acceptance["no_production_scan"] is True
