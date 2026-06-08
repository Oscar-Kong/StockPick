"""Shared metric transforms for factor scores (0–100)."""
from __future__ import annotations

from typing import Any


def clip100(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 50.0
    clipped = max(lo, min(hi, value))
    return max(0.0, min(100.0, 100.0 * (clipped - lo) / (hi - lo)))


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
