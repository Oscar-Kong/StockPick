"""Factor Discovery LLM provider abstraction."""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from config import (
    APP_ENV,
    FACTOR_DISCOVERY_LLM_MAX_RETRIES,
    FACTOR_DISCOVERY_LLM_MAX_TOKENS,
    FACTOR_DISCOVERY_LLM_TIMEOUT_SEC,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
)
import config as app_config
from services.factor_discovery.llm.errors import (
    FactorLlmProviderConfigurationError,
    FactorLlmStructuredOutputError,
    FactorLlmTimeoutError,
)
from services.factor_discovery.llm.models import FactorLlmRequestMetadata

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}", re.MULTILINE)

PROVIDER_EXISTING_DEFAULT = "existing_default"
PROVIDER_FIXTURE = "fixture"
PROVIDER_DISABLED = "disabled"


@dataclass(frozen=True)
class FactorLlmProviderResponse:
    provider_id: str
    model_id: str
    raw_text: str
    parsed: BaseModel
    input_token_count: int | None
    output_token_count: int | None
    total_token_count: int | None
    latency_ms: int
    finish_reason: str
    structured_output_mode: str
    retry_count: int
    provider_request_id: str | None = None


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(text)
        if m:
            return json.loads(m.group(0))
        raise FactorLlmStructuredOutputError("LLM_JSON_PARSE_FAILED", "could not parse JSON from LLM response")


class ExistingDefaultLlmClient:
    provider_id = PROVIDER_EXISTING_DEFAULT

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        request_metadata: FactorLlmRequestMetadata,
        max_tokens: int | None = None,
    ) -> FactorLlmProviderResponse:
        if not LLM_API_KEY:
            raise FactorLlmProviderConfigurationError("LLM_API_KEY_MISSING", "LLM API key not configured")
        from services.llm_explainer import _call_llm

        schema_name = response_schema.__name__
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_prompt
                + f"\n\nReturn ONLY valid JSON for schema {schema_name}. No markdown. No code execution.",
            },
        ]
        retries = 0
        last_exc: Exception | None = None
        start = time.monotonic()
        raw = ""
        for attempt in range(FACTOR_DISCOVERY_LLM_MAX_RETRIES + 1):
            try:
                raw = _call_llm(
                    messages,
                    max_tokens=max_tokens or FACTOR_DISCOVERY_LLM_MAX_TOKENS,
                    temperature=0.1,
                )
                payload = _extract_json(raw)
                parsed = response_schema.model_validate(payload)
                latency = int((time.monotonic() - start) * 1000)
                return FactorLlmProviderResponse(
                    provider_id=self.provider_id,
                    model_id=LLM_MODEL,
                    raw_text=raw[:8000],
                    parsed=parsed,
                    input_token_count=None,
                    output_token_count=None,
                    total_token_count=None,
                    latency_ms=latency,
                    finish_reason="stop",
                    structured_output_mode="prompt_json_pydantic",
                    retry_count=retries,
                    provider_request_id=f"fdllm_{uuid.uuid4().hex[:12]}",
                )
            except Exception as exc:
                last_exc = exc
                retries = attempt
                if attempt >= FACTOR_DISCOVERY_LLM_MAX_RETRIES:
                    break
        if isinstance(last_exc, json.JSONDecodeError):
            raise FactorLlmStructuredOutputError("LLM_JSON_PARSE_FAILED", str(last_exc)[:200]) from last_exc
        if "timeout" in str(last_exc).lower():
            raise FactorLlmTimeoutError("LLM_TIMEOUT", str(last_exc)[:200]) from last_exc
        raise FactorLlmStructuredOutputError("LLM_PROVIDER_FAILED", str(last_exc)[:200]) from last_exc


class DisabledLlmClient:
    provider_id = PROVIDER_DISABLED

    def generate_structured(self, **kwargs) -> FactorLlmProviderResponse:
        raise FactorLlmProviderConfigurationError("FACTOR_DISCOVERY_LLM_DISABLED", "LLM provider is disabled")


_fixture_responses: dict[str, BaseModel] = {}


def set_fixture_response(key: str, response: BaseModel) -> None:
    _fixture_responses[key] = response


def clear_fixture_responses() -> None:
    _fixture_responses.clear()


class FixtureLlmClient:
    provider_id = PROVIDER_FIXTURE

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        request_metadata: FactorLlmRequestMetadata,
        max_tokens: int | None = None,
    ) -> FactorLlmProviderResponse:
        key = request_metadata.operation_type.value
        if key not in _fixture_responses:
            raise FactorLlmStructuredOutputError("FIXTURE_RESPONSE_MISSING", key)
        parsed = _fixture_responses[key]
        if not isinstance(parsed, response_schema):
            parsed = response_schema.model_validate(parsed.model_dump(mode="json"))
        return FactorLlmProviderResponse(
            provider_id=self.provider_id,
            model_id="fixture-model-v1",
            raw_text=json.dumps(parsed.model_dump(mode="json")),
            parsed=parsed,
            input_token_count=100,
            output_token_count=200,
            total_token_count=300,
            latency_ms=1,
            finish_reason="stop",
            structured_output_mode="fixture",
            retry_count=0,
        )


def get_factor_discovery_llm_client(*, fixture_client=None):
    provider = app_config.FACTOR_DISCOVERY_LLM_PROVIDER
    if fixture_client is not None:
        return fixture_client
    if provider == PROVIDER_FIXTURE:
        if app_config.APP_ENV not in ("test", "development"):
            raise FactorLlmProviderConfigurationError("FIXTURE_LLM_FORBIDDEN", "fixture LLM not allowed in production")
        return FixtureLlmClient()
    if provider == PROVIDER_EXISTING_DEFAULT:
        return ExistingDefaultLlmClient()
    return DisabledLlmClient()
