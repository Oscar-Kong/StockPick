"""Staging provider activation tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from services.factor_discovery.data_provider import get_runtime_factor_research_provider
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.staging.provider_gate import provider_readiness_blockers, require_historical_store_for_staging
from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture


def test_historical_store_blocked_without_staging(isolated_backend_env, monkeypatch):
    seed_staging_fixture(variant="valid")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "historical_store", raising=False)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_STAGING_ENABLED", False, raising=False)
    monkeypatch.setattr(config, "APP_ENV", "development", raising=False)
    with pytest.raises(FactorDiscoveryError) as exc:
        require_historical_store_for_staging()
    assert exc.value.code == "STAGING_PROVIDER_BLOCKED"


def test_historical_store_allowed_in_test_env(isolated_backend_env, monkeypatch):
    seed_staging_fixture(variant="valid")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "historical_store", raising=False)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_STAGING_ENABLED", False, raising=False)
    monkeypatch.setattr(config, "APP_ENV", "test", raising=False)
    provider = get_runtime_factor_research_provider()
    assert provider.provider_id == "historical_store_v1"


def test_provider_readiness_blocks_disabled_default(isolated_backend_env, monkeypatch):
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "disabled", raising=False)
    blockers = provider_readiness_blockers()
    assert "data_provider_disabled" in blockers


def test_provider_readiness_includes_audit_blockers(isolated_backend_env, monkeypatch):
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "historical_store", raising=False)
    monkeypatch.setattr(config, "APP_ENV", "test", raising=False)
    blockers = provider_readiness_blockers()
    assert "universe_pit_empty" in blockers or "no_daily_quotes" in blockers
