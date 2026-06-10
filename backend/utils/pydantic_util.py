"""Pydantic v1/v2 serialization compatibility."""
from __future__ import annotations

from typing import Any


def model_to_dict(obj: Any, **kwargs: Any) -> dict[str, Any]:
    """Serialize a Pydantic model to dict (v1 `.dict()` or v2 `.model_dump()`)."""
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(**kwargs)
    if hasattr(obj, "dict"):
        return obj.dict(**kwargs)
    raise TypeError(f"Expected Pydantic model, got {type(obj)!r}")


def models_to_dicts(items: list[Any], **kwargs: Any) -> list[dict[str, Any]]:
    return [model_to_dict(item, **kwargs) for item in items]
