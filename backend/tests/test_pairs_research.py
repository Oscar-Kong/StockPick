"""Tests for pairs-trading research module."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.pairs.cointegration import engle_granger_test, statsmodels_available
from engines.pairs.spread import build_spread, estimate_half_life, spread_zscore
from services.pairs_research_service import analyze_pair, run_pairs_research


def _cointegrated_panel(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-03", periods=n)
    x = np.cumsum(rng.normal(0, 1, n)) + 100
    noise = rng.normal(0, 0.5, n)
    y = 1.8 * x + 10 + noise
    z = np.cumsum(rng.normal(0, 1, n)) + 50
    return pd.DataFrame({"AAA": y, "BBB": x, "CCC": z}, index=dates)


def test_build_spread_and_zscore():
    panel = _cointegrated_panel(120)
    spread = build_spread(panel["AAA"], panel["BBB"], hedge_ratio=1.8, intercept=10.0)
    zinfo = spread_zscore(spread, window=30)
    assert zinfo["sufficient"] is True
    assert zinfo["latest_z_score"] is not None
    assert abs(zinfo["latest_z_score"]) < 5


def test_half_life_mean_reverting_spread():
    rng = np.random.default_rng(0)
    n = 200
    s = [0.0]
    for _ in range(n - 1):
        s.append(s[-1] * 0.95 + rng.normal(0, 0.1))
    spread = pd.Series(s)
    hl = estimate_half_life(spread)
    assert hl["sufficient"] is True
    assert hl["mean_reverting"] is True
    assert hl["half_life_sessions"] is not None
    assert hl["half_life_sessions"] > 0


def test_engle_granger_cointegrated_pair():
    statsmodels = pytest.importorskip("statsmodels")
    _ = statsmodels  # noqa: F841
    panel = _cointegrated_panel(250)
    out = engle_granger_test(panel["AAA"], panel["BBB"])
    assert out["sufficient"] is True
    assert out["hedge_ratio"] == pytest.approx(1.8, abs=0.3)
    if statsmodels_available():
        assert out["engine"] == "statsmodels"
        assert out["p_value"] is not None
        assert out["p_value"] < 0.10
    else:
        assert out["engine"] == "fallback_adf"


def test_engle_granger_insufficient_data():
    out = engle_granger_test([1.0, 2.0], [1.0, 2.1])
    assert out["sufficient"] is False
    assert out["warning"] == "insufficient_observations"


def test_analyze_pair_output_shape():
    panel = _cointegrated_panel(200)
    row = analyze_pair("AAA", "BBB", panel, zscore_window=40)
    assert row["pair"] == ["AAA", "BBB"]
    assert row["symbol_y"] == "AAA"
    assert row["hedge_ratio"] is not None
    assert "p_value" in row
    assert "latest_z_score" in row
    assert "half_life_sessions" in row


def test_run_pairs_research_with_panel():
    panel = _cointegrated_panel(200)
    report = run_pairs_research(
        ["AAA", "BBB", "CCC"],
        lookback_period="1y",
        price_panel=panel,
        max_pairs=10,
    )
    assert report["research_only"] is True
    assert report["pairs_evaluated"] == 3
    assert len(report["pairs"]) == 3
    assert "not used for auto-trading" in report["notes"][0]
    if statsmodels_available():
        aaa_bbb = next(r for r in report["pairs"] if r["pair"] == ["AAA", "BBB"])
        assert aaa_bbb["sufficient"] is True
