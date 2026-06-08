"""Structured LLM extraction helpers — JSON signals only, no buy/sell."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


def _parse_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"summary": text[:500]}


def llm_json_extract(
    *,
    agent: str,
    symbol: str,
    context: str,
    schema_hint: str,
    max_tokens: int = 200,
) -> dict[str, Any]:
    from services.llm_explainer import _call_llm

    prompt = (
        f"You are the {agent} agent for equity research on {symbol}. "
        f"Return ONLY valid JSON. No buy/sell/hold recommendations. "
        f"Schema hint: {schema_hint}. Context: {context[:2000]}"
    )
    try:
        raw = _call_llm([{"role": "user", "content": prompt}], max_tokens=max_tokens)
        out = _parse_json(raw)
        out.setdefault("summary", str(raw)[:240])
        return out
    except Exception as exc:
        logger.debug("LLM extract failed %s: %s", agent, exc)
        return {"summary": context[:240], "error": str(exc)}


def enrich_fundamental(symbol: str, signals: dict[str, Any]) -> dict[str, Any]:
    return llm_json_extract(
        agent="fundamental_analyst",
        symbol=symbol,
        context=str(signals),
        schema_hint='{"quality_flags":[],"growth_note":"","summary":""}',
    )


def enrich_valuation(symbol: str, signals: dict[str, Any]) -> dict[str, Any]:
    return llm_json_extract(
        agent="valuation",
        symbol=symbol,
        context=str(signals),
        schema_hint='{"margin_of_safety_note":"","peer_context":"","summary":""}',
    )


def enrich_bear_case(symbol: str, summary: str) -> dict[str, Any]:
    return llm_json_extract(
        agent="bear_case",
        symbol=symbol,
        context=summary,
        schema_hint='{"risks":["..."],"summary":""}',
        max_tokens=160,
    )
