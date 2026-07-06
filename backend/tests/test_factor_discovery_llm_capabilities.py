"""Capability and feature-flag tests for Factor Discovery LLM."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from services.factor_discovery.llm.capabilities import assess_llm_capabilities, require_llm_operation
from services.factor_discovery.llm.client import get_factor_discovery_llm_client
from services.factor_discovery.llm.errors import FactorLlmCapabilityError, FactorLlmDisabledError, FactorLlmProviderConfigurationError
from services.factor_discovery.llm.models import LlmOperationType
from services.factor_discovery.operations import factor_discovery_operational_status


def test_llm_disabled_by_default():
    caps = assess_llm_capabilities()
    assert caps.llm_enabled is False
    assert "FACTOR_DISCOVERY_LLM_ENABLED=false" in caps.blocking_reasons
    assert "FACTOR_DISCOVERY_LLM_PROVIDER=disabled" in caps.blocking_reasons


def test_disabled_request_never_calls_client(monkeypatch):
    config.FACTOR_DISCOVERY_LLM_ENABLED.set(False)
    with pytest.raises(FactorLlmDisabledError):
        require_llm_operation(LlmOperationType.HYPOTHESIS_GENERATE)


def test_unknown_provider_rejected(monkeypatch):
    config.FACTOR_DISCOVERY_LLM_ENABLED.set(True)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_LLM_PROVIDER", "unknown_vendor", raising=False)
    caps = assess_llm_capabilities()
    assert any("unknown provider" in r for r in caps.blocking_reasons)
    with pytest.raises(FactorLlmCapabilityError):
        require_llm_operation(LlmOperationType.HYPOTHESIS_GENERATE)


def test_fixture_provider_blocked_in_production(monkeypatch):
    monkeypatch.setattr(config, "APP_ENV", "production", raising=False)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_LLM_PROVIDER", "fixture", raising=False)
    with pytest.raises(FactorLlmProviderConfigurationError) as exc:
        get_factor_discovery_llm_client()
    assert exc.value.code == "FIXTURE_LLM_FORBIDDEN"


def test_enabling_llm_does_not_enable_experiment_execution(monkeypatch):
    config.FACTOR_DISCOVERY_LLM_ENABLED.set(True)
    config.FACTOR_DISCOVERY_ENABLED.set(False)
    status = factor_discovery_operational_status()
    assert status["llm_feature_flag_enabled"] is True
    assert status["feature_flag_enabled"] is False


def test_operational_diagnostics_reflect_llm_caps(isolated_backend_env, monkeypatch):
    config.FACTOR_DISCOVERY_LLM_ENABLED.set(True)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_LLM_PROVIDER", "fixture", raising=False)
    status = factor_discovery_operational_status()
    assert "llm_capabilities" in status
    assert status["llm_provider"] == "fixture"
