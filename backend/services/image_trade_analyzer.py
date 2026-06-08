"""Analyze uploaded trade screenshots via LLM vision when available."""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import requests

from config import LLM_API_KEY, LLM_BASE_URL, LLM_ENABLED, LLM_MODEL

logger = logging.getLogger(__name__)

_PROMPT = (
    "You are a trade-journal assistant. Analyze this uploaded trading screenshot and return JSON only "
    "with keys: image_insight (string, <= 220 chars), image_tags (array of up to 6 short tags), "
    "confidence (low|medium|high). Do not invent broker/account details."
)


def _extract_json(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    try:
        return json.loads(candidate)
    except Exception:
        pass
    m = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def analyze_trade_screenshot(
    image_bytes: bytes,
    *,
    mime_type: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    if not LLM_API_KEY or not LLM_ENABLED:
        return {"image_insight": "", "image_tags": [], "analysis_status": "llm_not_configured"}
    if not image_bytes:
        return {"image_insight": "", "image_tags": [], "analysis_status": "empty_image"}

    mime = mime_type or "image/png"
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": _PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"filename={filename or 'upload'}"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "max_tokens": 180,
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=body, headers=headers, timeout=35)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = _extract_json(content) or {}
        insight = str(parsed.get("image_insight", "")).strip()[:220]
        tags = [str(t).strip() for t in (parsed.get("image_tags") or []) if str(t).strip()][:6]
        return {
            "image_insight": insight,
            "image_tags": tags,
            "analysis_status": "ok" if insight or tags else "empty_result",
        }
    except Exception as exc:
        logger.warning("Screenshot analysis unavailable: %s", exc)
        return {"image_insight": "", "image_tags": [], "analysis_status": "llm_vision_unavailable"}
