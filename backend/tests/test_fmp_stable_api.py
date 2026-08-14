"""FMP client must use stable endpoints (legacy /api/v3 returns 403 for new keys)."""
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


def test_fmp_get_uses_stable_base_url():
    client = FMPClient(api_key="test-key")
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = [{"symbol": "AAPL", "companyName": "Apple", "mktCap": 1}]

    with patch("data.fmp_client.requests.get", return_value=response) as get:
        client._get("profile", {"symbol": "AAPL"})

    url = get.call_args.args[0]
    assert "financialmodelingprep.com/stable/" in url
    assert "/api/v3/" not in url
    assert get.call_args.kwargs["params"]["symbol"] == "AAPL"
    assert get.call_args.kwargs["params"]["apikey"] == "test-key"


def test_legacy_endpoint_403_does_not_trip_circuit_breaker():
    client = FMPClient(api_key="test-key")
    response = MagicMock()
    response.status_code = 403
    response.text = (
        '{ "Error Message": "Legacy Endpoint : Due to Legacy endpoints being '
        'no longer supported - This endpoint is only available for legacy users" }'
    )
    err = __import__("requests").HTTPError(response=response)
    response.raise_for_status.side_effect = err

    with patch("data.fmp_client.requests.get", return_value=response):
        assert client._get("profile", {"symbol": "AAPL"}) is None

    assert FMPClient.is_disabled() is False


def test_get_history_fmp_parses_stable_list_payload():
    market = MarketDataClient(cache=MagicMock())
    market.fmp = MagicMock(api_key="test-key")
    market.fmp.get_historical_eod.return_value = [
        {
            "symbol": "AAPL",
            "date": "2026-07-24",
            "open": 100.0,
            "high": 110.0,
            "low": 95.0,
            "close": 105.0,
            "volume": 1_000_000,
        },
        {
            "symbol": "AAPL",
            "date": "2026-07-23",
            "open": 98.0,
            "high": 102.0,
            "low": 97.0,
            "close": 100.0,
            "volume": 900_000,
        },
    ]

    with patch("data.market_data_client.FMPClient.is_disabled", return_value=False):
        df = market._get_history_fmp("AAPL", period="5d")

    assert not df.empty
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    market.fmp.get_historical_eod.assert_called_once()
    assert market.fmp.get_historical_eod.call_args.args[0] == "AAPL"


def test_get_ratios_maps_stable_field_names():
    client = FMPClient(api_key="test-key", cache=MagicMock(get=MagicMock(return_value=None)))
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = [
        {
            "symbol": "AAPL",
            "priceToEarningsRatioTTM": 30.1,
            "priceToEarningsGrowthRatioTTM": 2.2,
            "priceToBookRatioTTM": 45.0,
            "netProfitMarginTTM": 0.25,
            "operatingProfitMarginTTM": 0.30,
            "debtToEquityRatioTTM": 1.5,
            "currentRatioTTM": 1.1,
        }
    ]

    with patch("data.fmp_client.requests.get", return_value=response):
        ratios = client.get_ratios("AAPL")

    assert ratios["pe_ratio"] == 30.1
    assert ratios["peg_ratio"] == 2.2
    assert ratios["debt_to_equity"] == 1.5
