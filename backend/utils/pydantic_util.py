"""Pydantic v1/v2 serialization compatibility."""
from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from utils.datetime_util import utc_iso_z


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


def _json_safe_float(value: float) -> float | None:
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def json_safe(obj: Any) -> Any:
    """Coerce values to JSON-serializable builtins.

    Handles nested dict/list/tuple, NumPy scalars/arrays, datetime/date, Decimal,
    Enum, set, bytes, and Pydantic models. Unknown types raise TypeError.
    """
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return [json_safe(v) for v in obj]
    if obj is None:
        return obj

    if isinstance(obj, datetime):
        return utc_iso_z(obj) or obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return _json_safe_float(float(obj))
    if isinstance(obj, Enum):
        return json_safe(obj.value)
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")

    # Pydantic models (avoid treating plain namespaces with model_dump as models only)
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return json_safe(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")) and type(obj).__module__.startswith(
        ("pydantic", "models")
    ):
        try:
            return json_safe(obj.dict())
        except Exception:
            pass

    mod = getattr(type(obj), "__module__", "") or ""
    type_name = type(obj).__name__
    if mod.startswith("numpy"):
        if type_name == "ndarray":
            return json_safe(obj.tolist())
        if type_name == "bool_" or type_name == "bool":
            return bool(obj)
        if type_name.startswith("int") or type_name.startswith("uint"):
            return int(obj)
        if type_name.startswith("float"):
            return _json_safe_float(float(obj))
        if type_name.startswith("datetime"):
            try:
                return json_safe(obj.astype("datetime64[ms]").item())
            except Exception:
                return str(obj)
        if hasattr(obj, "item"):
            try:
                return json_safe(obj.item())
            except Exception:
                pass

    # Exact builtins only — do not use isinstance(float/bool) (NumPy subclasses).
    if type(obj) is str:
        return obj
    if type(obj) is bool:
        return obj
    if type(obj) is int:
        return obj
    if type(obj) is float:
        return _json_safe_float(obj)

    if type_name in ("bool_",):
        return bool(obj)
    if type_name in ("int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64"):
        return int(obj)
    if type_name in ("float16", "float32", "float64"):
        return _json_safe_float(float(obj))
    if hasattr(obj, "item") and not isinstance(obj, (bytes, bytearray)):
        try:
            return json_safe(obj.item())
        except Exception:
            pass

    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
