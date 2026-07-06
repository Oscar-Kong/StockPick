"""Capability and policy validation for mining sessions."""
from __future__ import annotations

import config as app_config
from services.factor_discovery.llm.capabilities import assess_llm_capabilities
from services.factor_discovery.mining.errors import MiningFeatureDisabledError, MiningProviderCapabilityError
from services.factor_discovery.mining.models import MiningSessionMode


def require_mining_enabled() -> None:
    if not bool(app_config.FACTOR_DISCOVERY_LOOP_ENABLED):
        raise MiningFeatureDisabledError("FACTOR_DISCOVERY_LOOP_DISABLED", "FACTOR_DISCOVERY_LOOP_ENABLED is false")
    mode = app_config.FACTOR_DISCOVERY_LOOP_MODE
    if mode not in {MiningSessionMode.SUPERVISED.value, MiningSessionMode.BOUNDED_AUTO.value}:
        raise MiningFeatureDisabledError("MINING_MODE_DISABLED", f"FACTOR_DISCOVERY_LOOP_MODE={mode}")


def validate_session_mode(mode: str) -> None:
    if mode not in {MiningSessionMode.SUPERVISED.value, MiningSessionMode.BOUNDED_AUTO.value}:
        raise MiningProviderCapabilityError("INVALID_MINING_MODE", mode)


def require_mining_capabilities(*, llm_required: bool = True) -> None:
    require_mining_enabled()
    if not bool(app_config.FACTOR_DISCOVERY_ENABLED):
        raise MiningProviderCapabilityError("FACTOR_DISCOVERY_DISABLED", "FACTOR_DISCOVERY_ENABLED is false")
    if llm_required:
        if not bool(app_config.FACTOR_DISCOVERY_LLM_ENABLED):
            raise MiningProviderCapabilityError("FACTOR_DISCOVERY_LLM_DISABLED", "LLM required for mining loop")
        caps = assess_llm_capabilities()
        if caps.blocking_reasons:
            raise MiningProviderCapabilityError("LLM_CAPABILITY_FAILURE", ";".join(caps.blocking_reasons))
