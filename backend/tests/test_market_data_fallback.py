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
    kwargs = batch_mock.call_args.kwargs
    assert kwargs.get("max_runtime_seconds") is not None


def test_download_batch_skips_per_symbol_after_yf_bulk_hit():
    """After a partial yfinance bulk pass, do not burn minutes on per-symbol fallback."""
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
    market.fmp = None
    with (
        patch(
            "data.market_data_client.yf_client.download_batch",
            return_value={"AAA": yf_df},
        ),
        patch.object(market, "get_history") as get_history,
    ):
        result = market.download_batch(
            ["AAA", "BBB", "CCC"],
            period="6mo",
            max_runtime_seconds=30,
        )
    assert set(result.keys()) == {"AAA"}
    get_history.assert_not_called()
    assert market.last_batch_meta is not None
    assert market.last_batch_meta["requested"] == 3
    assert market.last_batch_meta["received"] == 1
    assert market.last_batch_meta["partial"] is True


def test_download_batch_fmp_fill_when_coverage_below_min():
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
    market.fmp = MagicMock(api_key="test")
    with (
        patch(
            "data.market_data_client.yf_client.download_batch",
            return_value={"AAA": yf_df},
        ),
        patch.object(market, "_get_history_fmp", return_value=yf_df) as fmp_hist,
        patch.object(market, "get_history") as get_history,
        patch("data.market_data_client.FMPClient.is_disabled", return_value=False),
        patch("data.market_data_client.SCAN_BULK_COVERAGE_MIN", 0.70),
    ):
        result = market.download_batch(
            ["AAA", "BBB", "CCC"],
            period="6mo",
            max_runtime_seconds=30,
        )
    assert set(result.keys()) == {"AAA", "BBB", "CCC"}
    assert fmp_hist.call_count == 2
    get_history.assert_not_called()
    assert market.last_batch_meta["source"] == "yfinance+fmp"
    assert market.last_batch_meta["partial"] is False


def test_download_batch_skips_per_symbol_when_yf_bulk_empty():
    """Rate-limited / empty bulk must not fall into Yahoo→AkShare per-symbol hammering."""
    market = MarketDataClient(cache=MagicMock(get_price_cache=MagicMock(return_value=None)))
    market.fmp = None
    with (
        patch("data.market_data_client.yf_client.download_batch", return_value={}),
        patch.object(market, "get_history") as get_history,
    ):
        result = market.download_batch(
            ["AAA", "BBB"],
            period="6mo",
            max_runtime_seconds=30,
            use_alpha_vantage_fallback=False,
            alpha_vantage_probe_symbols=0,
        )
    assert result == {}
    get_history.assert_not_called()
    assert market.last_batch_meta["partial"] is True

def test_yfinance_batch_stops_on_rate_limit():
    import data.yfinance_client as yf_mod

    calls = {"n": 0}

    def fake_process_timeout(fn, /, *args, timeout, **kwargs):
        calls["n"] += 1
        raise RuntimeError("Too Many Requests. Rate limited. Try after a while.")

    with (
        patch.object(yf_mod, "_import_yfinance", return_value=object()),
        patch("utils.process_timeout.run_with_process_timeout", side_effect=fake_process_timeout),
    ):
        out = yf_mod.download_batch(
            [f"S{i}" for i in range(80)],
            period="6mo",
            max_runtime_seconds=5,
        )
    assert out == {}
    assert calls["n"] == 1
