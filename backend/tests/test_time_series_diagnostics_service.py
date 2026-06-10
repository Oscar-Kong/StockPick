"""Tests for time_series_diagnostics_service."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.time_series_diagnostics_service import (
    build_time_series_diagnostics,
    interpret_log_returns,
    load_daily_closes,
)


def _closes(n: int = 260, drift: float = 0.0, noise: float = 0.01, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    prices = [100.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1.0 + drift + rng.normal(0, noise)))
    return pd.Series(prices)


@patch("data.historical_store.HistoricalStore")
def test_load_daily_closes_from_historical_store(mock_store_cls):
    closes = _closes(100)
    mock_store_cls.return_value.get_quotes.return_value = [
        {"date": f"2024-01-{i+1:02d}", "open": c, "high": c, "low": c, "close": float(c), "volume": 1e6}
        for i, c in enumerate(closes)
    ]

    series, source, notes = load_daily_closes("AAPL", 252)

    assert source == "historical_store"
    assert len(series) == 100
    assert notes


@patch("data.price_service.PriceService")
@patch("data.historical_store.HistoricalStore")
def test_load_daily_closes_fallback_price_service(mock_store_cls, mock_ps_cls):
    closes = _closes(200)
    hist = pd.DataFrame({"close": closes, "date": pd.date_range("2024-01-01", periods=200, freq="B")})
    mock_store_cls.return_value.get_quotes.return_value = []
    mock_ps_cls.return_value.get_history.return_value = hist

    series, source, _ = load_daily_closes("MSFT", 180)

    assert source == "price_service"
    assert len(series) == 180


def test_insufficient_data_short_series():
    with patch(
        "services.time_series_diagnostics_service.load_daily_closes",
        return_value=(pd.Series([100.0, 101.0, 102.0]), "price_service", []),
    ):
        out = build_time_series_diagnostics("TEST", lookback=252)

    assert out["interpretation"] == "insufficient data"
    assert out["sufficient_data"] is False
    assert out["annualized_volatility"] is None


def test_sufficient_data_shape():
    closes = _closes(260)
    with patch(
        "services.time_series_diagnostics_service.load_daily_closes",
        return_value=(closes, "historical_store", ["mock"]),
    ):
        out = build_time_series_diagnostics("AAPL", lookback=252)

    assert out["sufficient_data"] is True
    assert out["symbol"] == "AAPL"
    assert out["mean"] is not None
    assert out["annualized_volatility"] is not None
    assert out["skewness"] is not None
    assert out["excess_kurtosis"] is not None
    assert "jarque_bera" in out
    assert "adf" in out
    assert "autocorrelation" in out
    assert out["interpretation"] in {
        "mostly noise",
        "possible momentum",
        "possible mean reversion",
        "high tail risk",
        "insufficient data",
    }


def test_interpret_momentum():
    with patch(
        "services.time_series_diagnostics_service.autocorrelation_summary",
        return_value={"lag1": 0.15, "lags": [1], "acf": [0.15], "n": 120},
    ):
        phrase, notes = interpret_log_returns(pd.Series([0.01] * 120))
    assert phrase == "possible momentum"
    assert notes


def test_interpret_high_tail_risk():
    rng = np.random.default_rng(99)
    r = pd.Series(rng.standard_t(df=3, size=120) * 0.01)
    phrase, _ = interpret_log_returns(r)
    assert phrase == "high tail risk"


def test_interpret_insufficient():
    phrase, notes = interpret_log_returns(pd.Series([0.01, -0.01]))
    assert phrase == "insufficient data"
    assert notes


def test_route_diagnostics_response_model():
    from models.schemas import AnalyzeTimeSeriesDiagnosticsResponse

    closes = _closes(260)
    with patch(
        "services.time_series_diagnostics_service.load_daily_closes",
        return_value=(closes, "historical_store", []),
    ):
        data = build_time_series_diagnostics("NVDA", 252)
    model = AnalyzeTimeSeriesDiagnosticsResponse(**data)
    assert model.symbol == "NVDA"
    assert model.lookback == 252


if __name__ == "__main__":
    test_insufficient_data_short_series()
    test_sufficient_data_shape()
    test_interpret_insufficient()
    print("time_series_diagnostics_service tests passed")
