"""Tests for market data fallbacks when FMP is blocked."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.fmp_client import FMPClient
from data.market_data_client import MarketDataClient


@pytest.fixture(autouse=True)
def reset_fmp_circuit():
    FMPClient.reset_access_denied()
    yield
    FMPClient.reset_access_denied()


def test_fmp_circuit_breaker_trips_on_403():
    client = FMPClient(api_key="test-key")
    response = MagicMock()
    response.status_code = 403
    response.raise_for_status.side_effect = __import__("requests").HTTPError(response=response)

    with patch("data.fmp_client.requests.get", return_value=response):
        assert client._get("/profile/AAPL") is None
        assert FMPClient.is_disabled() is True
        assert client._get("/profile/MSFT") is None


def test_get_history_uses_yfinance_when_fmp_disabled():
    dates = pd.date_range("2025-01-01", periods=30, freq="B")
    yf_df = pd.DataFrame(
        {
            "date": dates,
            "open": [10.0] * 30,
            "high": [10.5] * 30,
            "low": [9.5] * 30,
            "close": [10.2] * 30,
            "volume": [1_000_000] * 30,
        }
    )
    FMPClient._access_denied = True
    market = MarketDataClient(cache=MagicMock(get_price_cache=MagicMock(return_value=None)))

    with patch("data.market_data_client.yf_client.get_history", return_value=yf_df) as yf_mock:
        df = market.get_history("AAPL", period="1mo")

    assert not df.empty
    yf_mock.assert_called_once_with("AAPL", period="1mo")


def test_download_batch_prefers_yfinance_bulk():
    dates = pd.date_range("2025-01-01", periods=30, freq="B")
    yf_df = pd.DataFrame(
        {
            "date": dates,
            "open": [5.0] * 30,
            "high": [5.5] * 30,
            "low": [4.5] * 30,
            "close": [5.2] * 30,
            "volume": [500_000] * 30,
        }
    )
    market = MarketDataClient(cache=MagicMock(get_price_cache=MagicMock(return_value=None)))

    with patch(
        "data.market_data_client.yf_client.download_batch",
        return_value={"AAA": yf_df, "BBB": yf_df},
    ) as batch_mock:
        result = market.download_batch(["AAA", "BBB"], period="6mo", max_runtime_seconds=5)

    assert set(result.keys()) == {"AAA", "BBB"}
    batch_mock.assert_called_once()
