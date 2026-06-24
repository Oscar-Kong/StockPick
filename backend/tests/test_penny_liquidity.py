"""Tests for penny liquidity metrics — raw ratios vs normalized scores."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.penny_liquidity import (
    compute_penny_liquidity_metrics,
    detect_penny_risk_warnings,
    relative_volume_components,
    relative_volume_ratio_from_df,
    relative_volume_score_from_ratio,
)
from scoring.technical import volume_spike_score


def _df(
    *,
    bars: int = 25,
    baseline_volume: float = 1_000_000.0,
    current_volume: float | None = None,
) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=bars, freq="B")
    volumes = [baseline_volume] * bars
    if current_volume is not None:
        volumes[-1] = current_volume
    closes = [2.0 + i * 0.01 for i in range(bars)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.05 for c in closes],
            "low": [c - 0.05 for c in closes],
            "close": closes,
            "volume": volumes,
        }
    )


@pytest.mark.parametrize(
    ("mult", "expected_ratio", "expected_score"),
    [
        (1.0, 1.0, 100 / 3),
        (2.0, 2.0, 200 / 3),
        (3.0, 3.0, 100.0),
        (5.0, 5.0, 100.0),
    ],
)
def test_relative_volume_ratios_and_scores(mult, expected_ratio, expected_score):
    df = _df(baseline_volume=1_000_000.0, current_volume=1_000_000.0 * mult)
    ratio = relative_volume_ratio_from_df(df)
    score = relative_volume_score_from_ratio(ratio)
    assert ratio == pytest.approx(expected_ratio)
    assert score == pytest.approx(expected_score)
    assert volume_spike_score(df) == pytest.approx(expected_score)


def test_current_bar_excluded_from_baseline():
    df = _df(baseline_volume=1_000_000.0, current_volume=3_000_000.0)
    baseline, current, ratio = relative_volume_components(df["volume"])
    manual_baseline = float(df["volume"].iloc[-21:-1].mean())
    assert manual_baseline == pytest.approx(1_000_000.0)
    assert current == pytest.approx(3_000_000.0)
    assert ratio == pytest.approx(3.0)
    assert baseline == pytest.approx(manual_baseline)


def test_zero_volume_baseline_returns_no_ratio():
    df = _df(baseline_volume=0.0, current_volume=500_000.0)
    ratio = relative_volume_ratio_from_df(df)
    metrics = compute_penny_liquidity_metrics(df)
    assert ratio is None
    assert metrics.relative_volume_score == 0.0
    assert "zero_volume_baseline" in metrics.warnings


def test_extremely_low_baseline_returns_no_ratio():
    df = _df(baseline_volume=50.0, current_volume=500_000.0)
    ratio = relative_volume_ratio_from_df(df)
    metrics = compute_penny_liquidity_metrics(df)
    assert ratio is None
    assert "extremely_low_volume_baseline" in metrics.warnings


def test_missing_current_volume():
    df = _df(baseline_volume=1_000_000.0)
    df.loc[df.index[-1], "volume"] = np.nan
    ratio = relative_volume_ratio_from_df(df)
    metrics = compute_penny_liquidity_metrics(df)
    assert ratio is None
    assert metrics.current_volume is None
    assert "missing_current_volume" in metrics.warnings


def test_raw_ratio_differs_from_score_display():
    """5x raw ratio must not be confused with a 0–100 score."""
    df = _df(baseline_volume=1_000_000.0, current_volume=5_000_000.0)
    metrics = compute_penny_liquidity_metrics(df)
    payload = metrics.to_metrics_dict()
    assert payload["relative_volume_ratio"] == pytest.approx(5.0)
    assert payload["relative_volume_score"] == pytest.approx(100.0)
    assert payload["volume_ratio"] == pytest.approx(5.0)
    assert payload["relative_volume_ratio"] != payload["relative_volume_score"]


def test_extreme_volume_outlier_score_capped_ratio_not():
    df = _df(baseline_volume=1_000_000.0, current_volume=10_000_000.0)
    ratio = relative_volume_ratio_from_df(df)
    score = relative_volume_score_from_ratio(ratio)
    assert ratio == pytest.approx(10.0)
    assert score == pytest.approx(100.0)


def test_to_metrics_dict_includes_dollar_volume_and_atr():
    df = _df(baseline_volume=2_000_000.0, current_volume=4_000_000.0)
    payload = compute_penny_liquidity_metrics(df).to_metrics_dict()
    assert payload["average_dollar_volume_20d"] > 0
    assert payload["atr_percent"] is not None
    assert payload["gap_percent"] is not None


def test_abnormal_volume_without_price_confirmation_warning():
    df = _df(baseline_volume=1_000_000.0, current_volume=4_000_000.0)
    metrics = compute_penny_liquidity_metrics(df)
    warns = detect_penny_risk_warnings(metrics, df, momentum_5d_score=48.0)
    assert "abnormal_volume_without_price_confirmation" in warns


def test_extreme_gap_warning():
    df = _df(baseline_volume=1_000_000.0)
    prev_close = float(df["close"].iloc[-2])
    df.loc[df.index[-1], "open"] = prev_close * 1.12
    metrics = compute_penny_liquidity_metrics(df)
    warns = detect_penny_risk_warnings(metrics, df, momentum_5d_score=70.0)
    assert "extreme_gap" in warns
