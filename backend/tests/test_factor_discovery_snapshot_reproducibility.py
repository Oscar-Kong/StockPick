"""Snapshot reproducibility and tampering tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from services.factor_discovery.artifact_integrity import ArtifactIntegrityError
from services.factor_discovery.data_provider import FixtureFactorResearchDataProvider
from services.factor_discovery.snapshot_service import FactorResearchSnapshotService, SnapshotRequest
from services.factor_discovery.staging.snapshot_reproducibility import FactorDiscoverySnapshotReproducibilityService
from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture
from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_validation_context


def test_fixture_snapshot_exact_match(isolated_backend_env, tmp_path):
    ctx = build_validation_context()
    provider = FixtureFactorResearchDataProvider(panel_builder=lambda: ctx["panel"])
    req = SnapshotRequest(
        provider_id="fixture_provider_v1",
        data_source_policy_id="research_adjusted_daily_v1",
        start_session=None,
        end_session=None,
        universe_source="fixture",
        required_fields=frozenset(),
        provider_data_version="fixture_v1",
    )
    repro = FactorDiscoverySnapshotReproducibilityService(storage_root=tmp_path)
    result = repro.verify_identical_request(provider, req)
    assert result.status == "EXACT_MATCH"
    assert result.panel_hash_match is True


def test_provider_version_changes_identity(isolated_backend_env):
    base = SnapshotRequest(
        provider_id="historical_store_v1",
        data_source_policy_id="research_adjusted_daily_v1",
        start_session="2020-01-02",
        end_session="2020-01-10",
        universe_source="universe_pit_v1",
        required_fields=frozenset({"adjusted_close"}),
        provider_data_version="v1",
    )
    svc = FactorDiscoverySnapshotReproducibilityService()
    changed = svc.verify_identity_changes_on_version_change(base, changed_provider_version="v2")
    assert changed["passed"] is True


def test_historical_store_snapshot_repro(isolated_backend_env, monkeypatch, tmp_path):
    seed_staging_fixture(variant="valid")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "historical_store", raising=False)
    from services.factor_discovery.data_provider import get_runtime_factor_research_provider
    from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities

    caps = assess_historical_store_capabilities()
    provider = get_runtime_factor_research_provider()
    req = SnapshotRequest(
        provider_id="historical_store_v1",
        data_source_policy_id="research_adjusted_daily_v1",
        start_session="2020-01-02",
        end_session="2020-01-10",
        universe_source="universe_pit_v1",
        required_fields=frozenset({"adjusted_close", "volume"}),
        provider_data_version=caps.provider_data_version,
    )
    repro = FactorDiscoverySnapshotReproducibilityService(storage_root=tmp_path)
    result = repro.verify_identical_request(provider, req)
    assert result.status == "EXACT_MATCH"


def test_tampering_detected(isolated_backend_env, tmp_path):
    ctx = build_validation_context()
    svc = FactorResearchSnapshotService(storage_root=tmp_path)
    provider = FixtureFactorResearchDataProvider(panel_builder=lambda: ctx["panel"])
    req = SnapshotRequest(
        provider_id="fixture_provider_v1",
        data_source_policy_id="research_adjusted_daily_v1",
        start_session=None,
        end_session=None,
        universe_source="fixture",
        required_fields=frozenset(),
        provider_data_version="fixture_v1",
    )
    snapshot_id, _, _ = svc.materialize(provider, req)
    row = svc._repo.get(snapshot_id)
    payload = json.loads(Path(row.storage_reference).read_text(encoding="utf-8"))
    payload["panel_csv"] = payload["panel_csv"].replace("100.", "999.", 1)
    Path(row.storage_reference).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ArtifactIntegrityError):
        svc.load_verified(snapshot_id)
