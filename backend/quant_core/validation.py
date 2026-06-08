"""Validation helpers for aligned time series and forward labels."""
from __future__ import annotations

import pandas as pd

from quant_core.returns import _as_series


def assert_aligned(a, b) -> None:
    """Raise ValueError when two series differ in length or index."""
    left = _as_series(a)
    right = _as_series(b)
    if len(left) != len(right):
        raise ValueError(f"Length mismatch: {len(left)} vs {len(right)}")
    if not left.index.equals(right.index):
        raise ValueError("Index mismatch between aligned series")


def validate_forward_labels(prices, labels, horizon: int) -> dict:
    """
    Sanity-check forward labels for look-ahead-safe usage.

    Returns a summary dict; raises ValueError on structural violations.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    p = _as_series(prices)
    y = _as_series(labels)
    assert_aligned(p, y)

    tail = y.iloc[-horizon:]
    if tail.notna().any():
        raise ValueError("Last `horizon` label rows must be NaN (undefined forward window)")

    # Spot-check: label at t equals price_{t+h}/price_t - 1 when both prices exist.
    if len(p) > horizon:
        t = len(p) - horizon - 1
        expected = p.iloc[t + horizon] / p.iloc[t] - 1.0
        actual = y.iloc[t]
        if pd.notna(actual) and abs(float(actual) - float(expected)) > 1e-12:
            raise ValueError(f"Label mismatch at index {t}: expected {expected}, got {actual}")

    return {
        "valid": True,
        "n": int(len(y)),
        "defined_labels": int(y.notna().sum()),
        "undefined_tail": int(horizon),
    }
