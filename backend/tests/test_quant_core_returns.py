"""Tests for quant_core.returns."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quant_core.returns import (
    annualized_return,
    annualized_volatility,
    cumulative_simple_return,
    excess_returns,
    log_returns,
    max_drawdown,
    rolling_return,
    simple_returns,
)


def _price_series() -> pd.Series:
    return pd.Series([100.0, 102.0, 101.0, 105.0, 110.0])


def test_simple_returns():
    r = simple_returns(_price_series())
    assert np.isnan(r.iloc[0])
    assert round(float(r.iloc[1]), 6) == round(0.02, 6)
    assert round(float(r.iloc[3]), 6) == round(105.0 / 101.0 - 1.0, 6)


def test_log_returns():
    p = _price_series()
    r = log_returns(p)
    expected = np.log(p.iloc[1] / p.iloc[0])
    assert round(float(r.iloc[1]), 8) == round(float(expected), 8)


def test_cumulative_simple_return():
    r = simple_returns(_price_series()).dropna()
    cum = cumulative_simple_return(r)
    assert round(float(cum.iloc[-1]), 6) == round(110.0 / 100.0 - 1.0, 6)


def test_rolling_return():
    p = _price_series()
    rr = rolling_return(p, window=2)
    assert np.isnan(rr.iloc[0])
    assert np.isnan(rr.iloc[1])
    assert round(float(rr.iloc[2]), 6) == round(101.0 / 100.0 - 1.0, 6)


def test_excess_returns():
    asset = pd.Series([0.02, 0.01, -0.01, 0.03])
    bench = pd.Series([0.01, 0.005, -0.02, 0.01])
    ex = excess_returns(asset, bench)
    assert len(ex) == 4
    assert round(float(ex.iloc[0]), 6) == 0.01
    assert round(float(ex.iloc[2]), 6) == 0.01


def test_annualized_return_and_volatility():
    r = pd.Series([0.01] * 252)
    ann = annualized_return(r, periods_per_year=252)
    assert ann > 0
    vol = annualized_volatility(r, periods_per_year=252)
    assert vol == pytest.approx(0.0, abs=1e-12)


def test_annualized_volatility_nonzero():
    r = pd.Series([0.01, -0.01, 0.02, -0.015, 0.005])
    vol = annualized_volatility(r, periods_per_year=252)
    assert vol > 0


def test_max_drawdown():
    equity = pd.Series([100.0, 110.0, 99.0, 105.0, 90.0, 95.0])
    dd = max_drawdown(equity)
    # Running peak 110 -> trough 90 => (90 - 110) / 110
    assert dd == pytest.approx((90.0 - 110.0) / 110.0, rel=1e-6)


def test_max_drawdown_monotonic_up():
    equity = pd.Series([1.0, 1.1, 1.2, 1.3])
    assert max_drawdown(equity) == 0.0


def test_invalid_window_raises():
    with pytest.raises(ValueError):
        rolling_return(_price_series(), window=0)


if __name__ == "__main__":
    test_simple_returns()
    test_log_returns()
    test_cumulative_simple_return()
    test_rolling_return()
    test_excess_returns()
    test_annualized_return_and_volatility()
    test_annualized_volatility_nonzero()
    test_max_drawdown()
    test_max_drawdown_monotonic_up()
    print("quant_core returns tests passed")
