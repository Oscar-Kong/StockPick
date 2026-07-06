"""Tests for volatility / VaR / ES risk engine."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.risk.engine import RiskEngine
from engines.risk.var_es import (
    historical_expected_shortfall,
    historical_var,
    tail_risk_flag,
)
from engines.risk.volatility import (
    assess_volatility_risk,
    ewma_volatility,
    realized_volatility,
    risk_penalty_from_volatility,
    volatility_regime,
)


def _returns(std: float = 0.01, n: int = 252, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.0, std, n))


def test_realized_volatility_known_level():
    r = _returns(std=0.01, n=300)
    vol = realized_volatility(r, window=21, annualized=True)
    assert vol is not None
    expected = 0.01 * np.sqrt(252)
    assert vol == pytest.approx(expected, rel=0.15)


def test_ewma_volatility_positive():
    r = _returns(std=0.012, n=200)
    vol = ewma_volatility(r, lambda_=0.94, annualized=True)
    assert vol is not None
    assert vol > 0


def test_historical_var_es_ordering():
    r = _returns(std=0.01, n=200)
    var = historical_var(r, alpha=0.05)
    es = historical_expected_shortfall(r, alpha=0.05)
    assert var is not None and es is not None
    assert es <= var


def test_tail_risk_with_crash():
    rng = np.random.default_rng(0)
    base = rng.normal(0.001, 0.008, 240)
    base[-5:] = [-0.12, -0.10, -0.08, -0.06, -0.05]
    r = pd.Series(base)
    var = historical_var(r, alpha=0.05)
    es = historical_expected_shortfall(r, alpha=0.05)
    assert tail_risk_flag(r, var=var, es=es) is True
    out = assess_volatility_risk(r)
    assert out["sufficient_data"] is True
    assert out["tail_risk"] is True
    assert out["risk_penalty_pts"] >= 3.0


def test_insufficient_data():
    r = pd.Series([0.01, -0.02, 0.005, 0.003])
    out = assess_volatility_risk(r)
    assert out["sufficient_data"] is False
    assert out["realized_volatility"] is None
    assert out["historical_var"] is None
    assert out["volatility_regime"] == "unknown"
    assert out["risk_penalty_pts"] == 0.0
    assert historical_var(r) is None


def test_volatility_regime_extreme():
    hist = [0.10, 0.11, 0.12, 0.13, 0.14, 0.15]
    assert volatility_regime(0.20, hist) == "extreme"
    assert volatility_regime(0.125, hist) == "normal"
    assert volatility_regime(0.08, hist) == "low"


def test_risk_penalty_from_volatility():
    assert risk_penalty_from_volatility("low", False) == 0.0
    assert risk_penalty_from_volatility("extreme", True) == 8.0


def test_risk_engine_applies_vol_penalty_when_v2_enabled():
    r = _returns(std=0.01, n=200)
    with patch("engines.risk.engine.compute_alerts", return_value=[]):
        with patch("engines.risk.engine.RISK_ENGINE_V2", True):
            assess = RiskEngine.assess(
                "TEST",
                "penny",
                final_score=75.0,
                apply_deduction=True,
                returns=r,
            )
    assert assess.volatility_risk.get("sufficient_data") is True
    if assess.volatility_risk.get("risk_penalty_pts", 0) > 0:
        assert any(item.get("type") == "volatility" for item in assess.breakdown)


def test_risk_engine_skips_vol_when_v2_disabled():
    r = _returns(std=0.01, n=200)
    with patch("engines.risk.engine.compute_alerts", return_value=[]):
        with patch("engines.risk.engine.RISK_ENGINE_V2", False):
            assess = RiskEngine.assess(
                "TEST",
                "penny",
                final_score=75.0,
                apply_deduction=False,
                returns=r,
            )
    assert assess.deduction_pts == 0.0


if __name__ == "__main__":
    test_realized_volatility_known_level()
    test_insufficient_data()
    test_tail_risk_with_crash()
    print("volatility risk tests passed")
