"""Quote/info Yahoo fallback and completeness-aware caching."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        # Force get_quote empty so FMP profile is used then filled
        with patch.object(market, "get_quote", return_value={"marketCap": None, "sector": None}):
            info = market.get_info("AAA")

    assert info["sector"] == "Technology"
    assert info["marketCap"] == 1_000_000
    assert info["currentPrice"] == 9.5
    assert info["trailingPE"] == 12.0
    # Completeness → long TTL
    cache.set.assert_called()
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
