"""JSON helpers for research foundation services."""
from __future__ import annotations

import json
from typing import Any


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def json_dumps(value: Any) -> str:
    return json.dumps(value, default=str)
