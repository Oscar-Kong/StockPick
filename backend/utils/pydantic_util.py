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


def json_safe(obj: Any) -> Any:
    """Coerce numpy scalars and nested structures for JSON serialization."""
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    mod = getattr(type(obj), "__module__", "") or ""
    if mod.startswith("numpy") and hasattr(obj, "item"):
        try:
            return json_safe(obj.item())
        except Exception:
            pass
    type_name = type(obj).__name__
    if type_name in ("bool_", "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64"):
        return int(obj)
    if type_name in ("float16", "float32", "float64"):
        return float(obj)
    if hasattr(obj, "item"):
        try:
            return json_safe(obj.item())
        except Exception:
            pass
    return obj
