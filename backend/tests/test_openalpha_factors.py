"""Tests for OpenAlpha-inspired factor operators and scorers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from engines.factor.expr import load_registry, registry_summary
from engines.factor.operators import cs_rank, ts_mean, ts_ols, ts_ret
from scoring.openalpha_factors import (
    score_openalpha_factor,
    vwap_close_gap_score,
    volume_return_corr_score,
)


def _ohlcv(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + rng.uniform(0.2, 1.0, n)
    low = close - rng.uniform(0.2, 1.0, n)
    vol = rng.integers(1_000_000, 5_000_000, n)
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        }
    )


def test_registry_loads():
    formulas = load_registry()
    assert len(formulas) >= 6
    summary = registry_summary()
    assert all(s["implemented"] for s in summary)


def test_ts_operators_finite():
    df = _ohlcv()
    ret = ts_ret(df["close"], 1)
    assert ret.notna().sum() > 50
    m = ts_mean(df["close"], 5)
    assert m.notna().sum() > 50
    _, _, resid = ts_ols(df["close"], ret, 10)
    assert resid.notna().sum() > 20


def test_openalpha_scores_in_range():
    df = _ohlcv()
    spy = df.copy()
    for key in ("vwap_close_gap", "ols_price_residual", "vol_ret_corr", "ret_autocorr", "vol_asymmetry"):
        s = score_openalpha_factor(key, df, spy)
        assert s is not None
        assert 0 <= s <= 100
    assert 0 <= vwap_close_gap_score(df) <= 100
    assert 0 <= volume_return_corr_score(df) <= 100


def test_cs_rank_bounds():
    s = cs_rank(pd.Series([1, 2, 3, 4, 5]))
    assert s.min() >= 0
    assert s.max() <= 1
