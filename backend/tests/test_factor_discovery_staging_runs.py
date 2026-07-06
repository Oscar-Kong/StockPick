"""Staging supervised run tests (historical_store + fixture DB)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from services.factor_discovery.staging.run_suite import FactorDiscoveryStagingRunSuite
from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture


@pytest.fixture
def staging_env(isolated_backend_env, monkeypatch, tmp_path):
    seed_staging_fixture(variant="long_history")
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "historical_store", raising=False)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_STAGING_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "FACTOR_RESEARCH_SNAPSHOT_ROOT", str(tmp_path / "snapshots"), raising=False)
    monkeypatch.setattr(config, "APP_ENV", "test", raising=False)


def test_materialize_and_run_frozen_factor(staging_env):
    suite = FactorDiscoveryStagingRunSuite()
    snap = suite.materialize_snapshot(start_session="2020-01-02", end_session="2020-07-01")
    assert not snap.get("blocking_codes")
    assert snap["reproducibility"]["status"] == "EXACT_MATCH"
    run = suite.run_supervised_experiment(snapshot_id=snap["snapshot_id"])
    assert run.get("status") == "completed"
    assert run.get("artifact_id")


def test_repeat_run_comparison(staging_env):
    suite = FactorDiscoveryStagingRunSuite()
    snap = suite.materialize_snapshot(start_session="2020-01-02", end_session="2020-07-01")
    run1 = suite.run_supervised_experiment(snapshot_id=snap["snapshot_id"], idempotency_key="run_a")
    run2 = suite.run_supervised_experiment(snapshot_id=snap["snapshot_id"], idempotency_key="run_b")
    comparison = suite.compare_repeat_runs(run1["run_id"], run2["run_id"])
    assert comparison["comparison_status"] in {"EXACT_MATCH", "SEMANTIC_MATCH_WITH_EXPECTED_CONTEXT_DIFFERENCE"}
    assert comparison["artifact_integrity_ok"] is True
