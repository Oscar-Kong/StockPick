"""Tests for factor exposure research module."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor_model.exposures import (
    build_return_matrix,
    estimate_market_betas,
    rolling_correlation_matrix,
)
from engines.factor_model.pca import pca_standardized_returns
from services.factor_exposure_service import build_factor_exposure_report


def _price_panel(n: int = 120, beta_map: dict[str, float] | None = None, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-02", periods=n)
    spy = np.cumprod(1 + rng.normal(0.0004, 0.01, n))
    data = {"SPY": spy}
    beta_map = beta_map or {"AAA": 1.2, "BBB": 0.8, "CCC": 1.5}
    for sym, beta in beta_map.items():
        noise = rng.normal(0, 0.005, n)
        rets = beta * np.diff(spy, prepend=spy[0]) / np.maximum(spy, 1e-6) + noise
        data[sym] = np.cumprod(1 + rets) * 100
    return pd.DataFrame(data, index=dates)


def test_build_return_matrix_shape():
    panel = _price_panel(80)
    rets = build_return_matrix(panel)
    assert rets.shape[0] == 79
    assert set(rets.columns) == {"SPY", "AAA", "BBB", "CCC"}


def test_estimate_market_betas_known_exposure():
    panel = _price_panel(200, beta_map={"AAA": 1.5, "BBB": 0.5})
    rets = build_return_matrix(panel)
    betas = estimate_market_betas(rets, "SPY")
    assert betas["AAA"]["sufficient"] is True
    assert betas["AAA"]["beta"] == pytest.approx(1.5, abs=0.35)
    assert betas["BBB"]["beta"] == pytest.approx(0.5, abs=0.35)


def test_rolling_correlation_matrix():
    panel = _price_panel(100)
    rets = build_return_matrix(panel)
    out = rolling_correlation_matrix(rets, window=30)
    assert out["sufficient"] is True
    assert "AAA" in out["matrix"]
    assert out["matrix"]["AAA"]["AAA"] == pytest.approx(1.0, abs=1e-6)


def test_pca_concentration_warning_on_correlated_series():
    rng = np.random.default_rng(0)
    n = 100
    dates = pd.bdate_range("2024-01-02", periods=n)
    factor = rng.normal(0, 0.02, n)
    rets = pd.DataFrame(
        {
            "A": factor + rng.normal(0, 0.002, n),
            "B": factor + rng.normal(0, 0.002, n),
            "C": factor + rng.normal(0, 0.002, n),
            "D": factor + rng.normal(0, 0.002, n),
            "SPY": rng.normal(0, 0.01, n),
        },
        index=dates,
    )
    out = pca_standardized_returns(rets[["A", "B", "C", "D"]], n_components=3, pc1_concentration_threshold=0.4)
    assert out["sufficient"] is True
    assert out["pc1_variance_ratio"] > 0.4
    assert out["concentration_warning"] is True
    assert len(out["symbol_loadings"]) == 4
    assert len(out["explained_variance_ratio"]) == 3


def test_pca_insufficient_data():
    rets = pd.DataFrame({"A": [0.01], "B": [0.02]})
    out = pca_standardized_returns(rets)
    assert out["sufficient"] is False


def test_build_factor_exposure_report_with_panel():
    panel = _price_panel(120)
    report = build_factor_exposure_report(
        ["AAA", "BBB", "CCC"],
        benchmark="SPY",
        lookback_period="1y",
        price_panel=panel,
    )
    assert report["diagnostic_only"] is True
    assert report["benchmark"] == "SPY"
    assert len(report["symbols_used"]) == 3
    assert report["observation_count"] > 30
    assert "AAA" in report["betas"]
    assert report["correlation"]["sufficient"] is True
    assert report["pca"]["sufficient"] is True
    assert "Diagnostic output only" in report["notes"][0]
