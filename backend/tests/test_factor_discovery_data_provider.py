"""Data provider capability and fixture isolation tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from services.factor_discovery.data_provider import (
    DisabledFactorResearchDataProvider,
    get_runtime_factor_research_provider,
)
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities


def test_disabled_provider_by_default(isolated_backend_env, monkeypatch):
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "disabled", raising=False)
    provider = get_runtime_factor_research_provider()
    assert isinstance(provider, DisabledFactorResearchDataProvider)
    with pytest.raises(FactorDiscoveryError) as exc:
        provider.load_snapshot(snapshot_id="x")
    assert exc.value.code == "FACTOR_RESEARCH_DATA_PROVIDER_NOT_CONFIGURED"


def test_fixture_forbidden_without_builder(isolated_backend_env, monkeypatch):
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "fixture", raising=False)
    monkeypatch.setattr(config, "APP_ENV", "test", raising=False)
    with pytest.raises(FactorDiscoveryError) as exc:
        get_runtime_factor_research_provider()
    assert exc.value.code == "FIXTURE_BUILDER_REQUIRED"


def test_historical_capabilities_on_empty_db(isolated_backend_env):
    caps = assess_historical_store_capabilities()
    assert caps.pit_universe_available is False
    assert "universe_pit_empty" in caps.blocking_reasons


def test_snapshot_tampering_detected(isolated_backend_env, tmp_path):
    import json

    from services.factor_discovery.artifact_integrity import ArtifactIntegrityError
    from services.factor_discovery.data_provider import FixtureFactorResearchDataProvider
    from services.factor_discovery.snapshot_service import FactorResearchSnapshotService, SnapshotRequest
    from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_validation_context

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
