"""Quote/info Yahoo fallback and completeness-aware caching."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.market_data_client import MarketDataClient


def test_get_info_fills_none_from_av_and_yahoo():
    cache = MagicMock()
    cache.get.return_value = None
    market = MarketDataClient(cache=cache)
    market.finnhub = None
    market.ak = None
    market.fmp = MagicMock()
    market.fmp.get_profile.return_value = {"marketCap": None, "sector": None, "price": None}
    market.fmp.get_ratios.return_value = {}
    market.av = MagicMock()
    market.av.get_overview.return_value = {
        "name": "Acme",
        "sector": "Technology",
        "market_cap": 1_000_000,
        "pe_ratio": 12.0,
    }

    with patch(
        "data.market_data_client.yf_client.get_info",
        return_value={
            "currentPrice": 9.5,
            "marketCap": 1_000_000,
            "sector": "Technology",
            "source": "yfinance",
        },
    ):
        with patch.object(market, "get_quote", return_value={"marketCap": None, "sector": None}):
            info = market.get_info("AAA")

    assert info["sector"] == "Technology"
    assert info["marketCap"] == 1_000_000
    assert info["currentPrice"] == 9.5
    assert info["trailingPE"] == 12.0
    # price + mcap + sector + PE → full 24h
    assert cache.set.call_args.args[2] == 86400


def test_get_info_empty_uses_short_ttl():
    cache = MagicMock()
    cache.get.return_value = None
    market = MarketDataClient(cache=cache)
    market.finnhub = None
    market.ak = None
    market.fmp = None
    market.av = None

    with (
        patch.object(market, "get_quote", return_value={}),
        patch("data.market_data_client.yf_client.get_info", return_value={}),
    ):
        info = market.get_info("ZZZ")

    assert not info.get("currentPrice")
    assert not info.get("marketCap")
    assert cache.set.call_args.args[2] == 300


def test_get_info_mcap_only_uses_mid_ttl():
    cache = MagicMock()
    cache.get.return_value = None
    market = MarketDataClient(cache=cache)
    market.finnhub = None
    market.ak = None
    market.fmp = None
    market.av = None

    with (
        patch.object(market, "get_quote", return_value={"marketCap": 100_000_000}),
        patch("data.market_data_client.yf_client.get_info", return_value={}),
    ):
        market.get_info("HALF")

    assert cache.set.call_args.args[2] == 900


def test_get_info_price_and_mcap_sparse_uses_hour_ttl():
    cache = MagicMock()
    cache.get.return_value = None
    market = MarketDataClient(cache=cache)
    market.finnhub = None
    market.ak = None
    market.fmp = None
    market.av = None

    with (
        patch.object(
            market,
            "get_quote",
            return_value={"currentPrice": 5.0, "marketCap": 100_000_000, "sector": ""},
        ),
        patch("data.market_data_client.yf_client.get_info", return_value={}),
    ):
        market.get_info("SPARSE")

    assert cache.set.call_args.args[2] == 3600


def test_get_quote_falls_back_to_yahoo():
    market = MarketDataClient(cache=MagicMock())
    market.finnhub = None
    market.ak = None
    market.fmp = None
    with patch(
        "data.market_data_client.yf_client.get_info",
        return_value={"currentPrice": 3.0, "marketCap": 100, "source": "yfinance"},
    ) as yf:
        quote = market.get_quote("YHOO")
    assert quote["currentPrice"] == 3.0
    yf.assert_called_once_with("YHOO")


def test_yfinance_get_info_timeout_returns_empty():
    import data.yfinance_client as yf_mod

    with (
        patch.object(yf_mod, "_import_yfinance", return_value=object()),
        patch(
            "utils.process_timeout.run_with_process_timeout",
            side_effect=TimeoutError("timed out"),
        ),
    ):
        assert yf_mod.get_info("AAA") == {}


def test_download_batch_respects_deadline_on_per_symbol_path():
    """PRIMARY=fmp path checks deadline before each symbol."""
    market = MarketDataClient(cache=MagicMock(get_price_cache=MagicMock(return_value=None)))
    market.fmp = MagicMock(api_key="x")
    calls = {"n": 0}

    def slow_history(sym, period="6mo", **kwargs):
        calls["n"] += 1
        time.sleep(0.25)
        dates = pd.date_range("2025-01-01", periods=5, freq="B")
        return pd.DataFrame(
            {
                "date": dates,
                "open": [1.0] * 5,
                "high": [1.0] * 5,
                "low": [1.0] * 5,
                "close": [1.0] * 5,
                "volume": [100] * 5,
            }
        )

    with (
        patch("data.market_data_client.PRIMARY_PRICE_SOURCE", "fmp"),
        patch("data.market_data_client.FMPClient.is_disabled", return_value=False),
        patch.object(market, "get_history", side_effect=slow_history),
    ):
        started = time.monotonic()
        result = market.download_batch(
            [f"S{i}" for i in range(20)],
            period="6mo",
            chunk_size=50,
            max_runtime_seconds=1,
            use_alpha_vantage_fallback=False,
            alpha_vantage_probe_symbols=0,
        )
    elapsed = time.monotonic() - started
    assert elapsed < 2.5
    assert calls["n"] < 20
    assert len(result) < 20
