"""Ops: numpy scalars and common Python types must not break JSON persistence."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.pydantic_util import json_safe


def test_json_safe_converts_numpy_bool_float_int():
    payload = {
        "ok": np.bool_(True),
        "flag": np.bool_(False),
        "score": np.float64(95.2),
        "n": np.int64(3),
        "nested": [{"x": np.float32(1.5), "y": np.bool_(True)}],
    }
    safe = json_safe(payload)
    assert safe["ok"] is True
    assert safe["flag"] is False
    assert type(safe["ok"]) is bool
    assert type(safe["score"]) is float
    assert type(safe["n"]) is int
    assert abs(safe["score"] - 95.2) < 1e-6
    assert safe["nested"][0]["y"] is True
    assert json.loads(json.dumps(safe))["ok"] is True


def test_json_safe_does_not_pass_through_numpy_float_as_python_float():
    value = np.float64(88.0)
    assert isinstance(value, float)
    safe = json_safe(value)
    assert type(safe) is float
    json.dumps({"v": safe})


def test_json_safe_datetime_date_decimal_enum_set_ndarray():
    class Color(Enum):
        RED = "red"

    payload = {
        "dt": datetime(2026, 6, 11, 9, 0, 0, tzinfo=timezone.utc),
        "d": date(2026, 6, 11),
        "dec": Decimal("12.5"),
        "color": Color.RED,
        "tags": {"a", "b"},
        "arr": np.array([1.0, 2.0]),
        "nan": float("nan"),
    }
    safe = json_safe(payload)
    assert safe["dt"].endswith("Z")
    assert safe["d"] == "2026-06-11"
    assert safe["dec"] == 12.5
    assert safe["color"] == "red"
    assert sorted(safe["tags"]) == ["a", "b"]
    assert safe["arr"] == [1.0, 2.0]
    assert safe["nan"] is None
    json.dumps(safe)


def test_json_safe_unknown_type_raises():
    class Weird:
        pass

    with pytest.raises(TypeError, match="Weird"):
        json_safe(Weird())
