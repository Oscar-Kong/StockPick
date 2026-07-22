"""Ops: numpy scalars must not break scan JSON persistence / FastAPI responses."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

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
    # Must survive stdlib JSON (scan cache path uses json.dumps).
    assert json.loads(json.dumps(safe))["ok"] is True


def test_json_safe_does_not_pass_through_numpy_float_as_python_float():
    """np.float64 is isinstance(float) on many builds — still must coerce for dumps."""
    value = np.float64(88.0)
    assert isinstance(value, float)
    safe = json_safe(value)
    assert type(safe) is float
    json.dumps({"v": safe})
