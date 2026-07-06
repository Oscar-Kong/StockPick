"""LLM capability validation for Factor Discovery."""
from __future__ import annotations

from dataclasses import dataclass

from config import (
    FACTOR_DISCOVERY_LLM_ENABLED,
    FACTOR_DISCOVERY_LLM_MAX_TOKENS,
    FACTOR_DISCOVERY_LLM_TIMEOUT_SEC,
    LLM_API_KEY,
    LLM_MODEL,
)
import config as app_config
from services.factor_discovery.llm.client import PROVIDER_DISABLED, PROVIDER_EXISTING_DEFAULT, PROVIDER_FIXTURE
from services.factor_discovery.llm.errors import FactorLlmCapabilityError, FactorLlmDisabledError
from services.factor_discovery.llm.models import LlmOperationType


@dataclass(frozen=True)
class FactorDiscoveryLlmCapabilities:
    llm_enabled: bool
    provider_configured: str
    model_configured: str | None
    structured_json_available: bool
    max_output_tokens: int
    timeout_sec: float
    hypothesis_generation_supported: bool
    dsl_translation_supported: bool
    critique_supported: bool
    run_interpretation_supported: bool
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def assess_llm_capabilities() -> FactorDiscoveryLlmCapabilities:
    blocking: list[str] = []
    warnings: list[str] = []
    if not bool(FACTOR_DISCOVERY_LLM_ENABLED):
        blocking.append("FACTOR_DISCOVERY_LLM_ENABLED=false")
    provider = app_config.FACTOR_DISCOVERY_LLM_PROVIDER
    if provider == PROVIDER_DISABLED:
        blocking.append("FACTOR_DISCOVERY_LLM_PROVIDER=disabled")
    elif provider == PROVIDER_EXISTING_DEFAULT and not LLM_API_KEY:
        blocking.append("LLM_API_KEY missing")
    elif provider not in {PROVIDER_DISABLED, PROVIDER_EXISTING_DEFAULT, PROVIDER_FIXTURE}:
        blocking.append(f"unknown provider: {provider}")
    if provider == PROVIDER_FIXTURE:
        warnings.append("fixture provider is test-only")
    return FactorDiscoveryLlmCapabilities(
        llm_enabled=bool(FACTOR_DISCOVERY_LLM_ENABLED),
        provider_configured=provider,
        model_configured=LLM_MODEL if provider != PROVIDER_DISABLED else None,
        structured_json_available=provider in {PROVIDER_EXISTING_DEFAULT, PROVIDER_FIXTURE},
        max_output_tokens=FACTOR_DISCOVERY_LLM_MAX_TOKENS,
        timeout_sec=FACTOR_DISCOVERY_LLM_TIMEOUT_SEC,
        hypothesis_generation_supported=len(blocking) == 0,
        dsl_translation_supported=len(blocking) == 0,
        critique_supported=len(blocking) == 0,
        run_interpretation_supported=len(blocking) == 0,
        blocking_reasons=tuple(blocking),
        warnings=tuple(warnings),
    )


def require_llm_operation(operation: LlmOperationType) -> None:
    caps = assess_llm_capabilities()
    if not caps.llm_enabled:
        raise FactorLlmDisabledError("FACTOR_DISCOVERY_LLM_DISABLED", "FACTOR_DISCOVERY_LLM_ENABLED is false")
    if caps.blocking_reasons:
        raise FactorLlmCapabilityError("LLM_CAPABILITY_FAILURE", ";".join(caps.blocking_reasons))
