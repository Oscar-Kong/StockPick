"""Strict MCP CallToolResult decoding for Robinhood tools.

Never treat tool-level errors as successful data. Prefer structuredContent
when present (MCP allows human-readable content alongside machine-readable
structured payloads).
"""
from __future__ import annotations

import json
import re
from typing import Any

_RETRYABLE_MARKERS = (
    "rate_limit",
    "rate limit",
    "too many requests",
    "429",
    "502",
    "503",
    "504",
    "timeout",
    "temporar",
    "unavailable",
    "connection reset",
    "connection refused",
    "try again",
)


class RobinhoodToolError(Exception):
    """MCP tool returned isError=true or an unusable error payload."""

    def __init__(
        self,
        *,
        tool: str,
        message: str,
        retryable: bool = False,
    ) -> None:
        self.tool = tool
        self.message = message
        self.retryable = retryable
        super().__init__(f"{tool}: {message}")


def is_retryable_error_message(message: str) -> bool:
    lowered = (message or "").lower()
    return any(marker in lowered for marker in _RETRYABLE_MARKERS)


def extract_error_message(content: Any) -> str:
    """Best-effort human/machine error text from CallToolResult.content."""
    chunks = _content_chunks(content)
    if not chunks:
        return "MCP tool returned isError without details"
    parts: list[str] = []
    for chunk in chunks:
        parsed = _extract_json(chunk)
        if isinstance(parsed, dict):
            for key in ("error", "message", "detail", "text"):
                val = parsed.get(key)
                if val is not None and str(val).strip():
                    parts.append(str(val).strip())
                    break
            else:
                parts.append(json.dumps(parsed, default=str)[:400])
        else:
            parts.append(str(parsed)[:400])
    return "; ".join(parts) if parts else "MCP tool returned isError"


def _extract_json(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, (dict, list)):
        return payload
    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            return {"binary": True, "size": len(payload)}
    text = str(payload).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


def _content_chunks(content: Any) -> list[Any]:
    blocks = content or []
    chunks: list[Any] = []
    for block in blocks:
        if hasattr(block, "text"):
            text = getattr(block, "text")
            if text is not None:
                chunks.append(text)
        elif isinstance(block, dict) and block.get("text") is not None:
            chunks.append(block["text"])
        elif hasattr(block, "data"):
            data = getattr(block, "data")
            if data is not None:
                chunks.append(data)
        elif isinstance(block, dict) and block.get("data") is not None:
            chunks.append(block["data"])
    return chunks


def _merge_blocks(parsed_blocks: list[Any]) -> Any:
    """Normalize multiple content blocks into one envelope parsers can read."""
    if not parsed_blocks:
        return None
    if len(parsed_blocks) == 1:
        return parsed_blocks[0]

    merged: dict[str, Any] = {}
    for block in parsed_blocks:
        if isinstance(block, dict):
            for key, value in block.items():
                if key not in merged or merged[key] in (None, "", [], {}):
                    merged[key] = value
                elif key in ("cursor", "next_cursor") and not merged.get(key):
                    merged[key] = value
        elif isinstance(block, list):
            existing = merged.get("items")
            if isinstance(existing, list):
                existing.extend(block)
            elif "items" not in merged:
                merged["items"] = list(block)

    return {"blocks": parsed_blocks, **merged} if merged else {"blocks": parsed_blocks}


def decode_tool_result(result: Any, *, tool: str = "unknown") -> Any:
    """Decode a CallToolResult into JSON-compatible data.

    Priority:
    1. isError → raise RobinhoodToolError
    2. structuredContent when present
    3. typed content blocks (merged when multiple)
    """
    is_error = bool(getattr(result, "isError", None) or getattr(result, "is_error", False))
    if is_error:
        message = extract_error_message(getattr(result, "content", None))
        raise RobinhoodToolError(
            tool=tool,
            message=message,
            retryable=is_retryable_error_message(message),
        )

    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured

    chunks = _content_chunks(getattr(result, "content", None))
    if not chunks:
        return None

    parsed = [_extract_json(c) for c in chunks]
    if len(parsed) == 1:
        return parsed[0] if parsed[0] is not None else chunks[0]
    return _merge_blocks(parsed)


_TICKER_KEY_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,11}$")


def looks_like_ticker(key: str) -> bool:
    text = str(key or "").strip().upper()
    if not text or text in {
        "POSITIONS",
        "EQUITY_POSITIONS",
        "HOLDINGS",
        "RESULTS",
        "DATA",
        "ITEMS",
        "ACCOUNTS",
        "ORDERS",
        "PORTFOLIO",
        "META",
        "CURSOR",
        "NEXT_CURSOR",
        "ERROR",
        "MESSAGE",
        "TEXT",
        "BLOCKS",
        "MERGED",
    }:
        return False
    return bool(_TICKER_KEY_RE.match(text))


def positions_payload_is_genuinely_empty(payload: Any) -> bool:
    """True when a successful positions response clearly has no holdings."""
    if payload is None:
        return True
    if isinstance(payload, list):
        return len(payload) == 0
    if not isinstance(payload, dict):
        return False
    if payload.get("error") or payload.get("isError") or payload.get("is_error"):
        return False
    for key in ("positions", "equity_positions", "holdings", "results", "items"):
        if key in payload:
            val = payload[key]
            if isinstance(val, list):
                return len(val) == 0
            if isinstance(val, dict):
                return len(val) == 0
            return False
    data = payload.get("data")
    if isinstance(data, dict):
        return positions_payload_is_genuinely_empty(data)
    if isinstance(data, list):
        return len(data) == 0
    # Non-empty dict with no known empty container — treat as not-empty for safety
    return len(payload) == 0
