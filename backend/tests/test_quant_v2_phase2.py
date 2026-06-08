"""Phase 2 unit tests — regimes, overlays, weight math (no market data)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.weighting.regime_classifier import (
    RegimeFeatures,
    classify_features,
    classify_spy,
)
from engines.weighting.regime_overlays import overlay_multiplier
from engines.factor.catalog import static_weights
from engines.weighting.weight_estimator import apply_regime_overlay


def _synthetic_spy_bull() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=260, freq="B")
    close = pd.Series(range(100, 100 + len(dates)), index=dates, dtype=float) + 50.0
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1_000_000,
        }
    )


def test_classify_bull_from_features():
    f = RegimeFeatures(
        as_of_date="2026-06-01",
        price=200.0,
        r6m=0.12,
        sigma_20d_ann=0.18,
        ma50=190.0,
        ma200=170.0,
        slope_50d=0.001,
        above_ma200=True,
    )
    assert classify_features(f) == "bull"


def test_classify_high_vol_priority():
    f = RegimeFeatures(
        as_of_date="2026-06-01",
        price=200.0,
        r6m=0.12,
        sigma_20d_ann=0.30,
        ma50=190.0,
        ma200=170.0,
        slope_50d=0.001,
        above_ma200=True,
    )
    assert classify_features(f) == "high_vol"


def test_classify_spy_dataframe():
    result = classify_spy(_synthetic_spy_bull())
    assert result is not None
    assert result.regime in ("bull", "low_vol", "neutral", "sideways")


def test_overlay_defaults_one():
    assert overlay_multiplier("medium", "bull", "medium_qlib_alpha") == 1.0
    assert overlay_multiplier("medium", "bull", "medium_rs_vs_spy") == 1.25


def test_regime_overlay_renormalizes():
    base = {"medium_rs_vs_spy": 0.5, "medium_sentiment": 0.5}
    out = apply_regime_overlay(base, "medium", "bull")
    assert abs(sum(out.values()) - 1.0) < 1e-6


def test_static_weights_sum():
    w = static_weights("penny")
    assert abs(sum(w.values()) - 1.0) < 1e-6
    assert "penny_momentum_5d" in w


if __name__ == "__main__":
    test_classify_bull_from_features()
    test_classify_high_vol_priority()
    test_classify_spy_dataframe()
    test_overlay_defaults_one()
    test_regime_overlay_renormalizes()
    test_static_weights_sum()
    print("quant v2 phase2 tests passed")
