"""Tests for quant_core.labels — forward labels and no look-ahead leakage."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quant_core.features import lag, rolling_mean
from quant_core.labels import (
    forward_excess_return_label,
    forward_return_label,
    large_move_label,
)
from quant_core.validation import assert_aligned, validate_forward_labels


def _prices(n: int = 8, start: float = 100.0, step: float = 1.0) -> pd.Series:
    return pd.Series([start + step * i for i in range(n)])


def test_forward_return_label_values():
    p = _prices()
    h = 2
    labels = forward_return_label(p, horizon=h)
    # t=0: p2/p0 - 1
    expected_0 = p.iloc[2] / p.iloc[0] - 1.0
    assert round(float(labels.iloc[0]), 8) == round(float(expected_0), 8)
    assert labels.iloc[-h:].isna().all()
    assert labels.iloc[: len(p) - h].notna().all()


def test_forward_return_no_lookahead_in_features():
    """Features at t must not include prices after t; labels may use t+h."""
    p = _prices()
    h = 3
    labels = forward_return_label(p, horizon=h)
    feature = rolling_mean(lag(p, 1), window=2)

    t = 2
    assert feature.iloc[t] == pytest.approx((p.iloc[1] + p.iloc[0]) / 2.0)
    assert labels.iloc[t] == pytest.approx(p.iloc[t + h] / p.iloc[t] - 1.0)
    # Feature at t uses only p[0..t]; label uses p[t+h] — no overlap in feature construction.
    assert t + h > t


def test_validate_forward_labels_passes():
    p = _prices()
    h = 2
    labels = forward_return_label(p, horizon=h)
    summary = validate_forward_labels(p, labels, horizon=h)
    assert summary["valid"] is True
    assert summary["undefined_tail"] == h
    assert summary["defined_labels"] == len(p) - h


def test_validate_forward_labels_rejects_bad_tail():
    p = _prices()
    h = 2
    labels = forward_return_label(p, horizon=h)
    labels.iloc[-1] = 0.01
    with pytest.raises(ValueError, match="Last `horizon` label rows must be NaN"):
        validate_forward_labels(p, labels, horizon=h)


def test_forward_excess_return_label():
    asset = _prices(n=6, start=100.0, step=2.0)
    bench = _prices(n=6, start=100.0, step=1.0)
    h = 2
    excess = forward_excess_return_label(asset, bench, horizon=h)
    asset_fwd = forward_return_label(asset, h)
    bench_fwd = forward_return_label(bench, h)
    assert excess.iloc[0] == pytest.approx(asset_fwd.iloc[0] - bench_fwd.iloc[0])
    assert excess.iloc[-h:].isna().all()


def test_large_move_label():
    p = pd.Series([100.0, 100.0, 120.0, 121.0, 122.0])
    h = 1
    labels = large_move_label(p, horizon=h, threshold=0.15)
    # t=1 forward return: 120/100 - 1 = 20%
    assert labels.iloc[1] == 1.0
    assert labels.iloc[-1] is np.nan or pd.isna(labels.iloc[-1])


def test_assert_aligned_rejects_mismatch():
    a = pd.Series([1.0, 2.0], index=[0, 1])
    b = pd.Series([1.0, 2.0], index=[0, 2])
    with pytest.raises(ValueError, match="Index mismatch"):
        assert_aligned(a, b)


if __name__ == "__main__":
    test_forward_return_label_values()
    test_forward_return_no_lookahead_in_features()
    test_validate_forward_labels_passes()
    test_validate_forward_labels_rejects_bad_tail()
    test_forward_excess_return_label()
    test_large_move_label()
    test_assert_aligned_rejects_mismatch()
    print("quant_core labels tests passed")
