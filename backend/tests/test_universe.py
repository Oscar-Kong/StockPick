"""Tests for universe construction, listing master parsing, and cache invalidation."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import listing_master as lm
from data.cache import Cache, init_db
from data.universe import (
    LARGE_CAP_SEEDS,
    PENNY_DISCOVERY_SEEDS,
    SECTOR_ETFS,
    STALE_OR_DELISTED,
    SYMBOL_THEMES,
    TICKER_ALIASES,
    _get_universe_cached,
    cap_universe_for_scan,
    get_universe,
    get_universe_revision,
    normalize_symbol,
)

NASDAQ_FIXTURE = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. Common Stock|Q|N|N|100|N|N
TESTY|Test Issue Corp|G|Y|N|100|N|N
SPY|SPDR S&P 500 ETF Trust|G|N|N|100|Y|N
AACBR|Artius II Acquisition Inc. - Rights|G|N|N|100|N|N
AACBU|Artius II Acquisition Inc. - Units|G|N|N|100|N|N
XYZ|Block, Inc. Class A Common Stock|Q|N|N|100|N|N
BRK.B|Berkshire Hathaway Inc. New Common Stock|Q|N|N|40|N|N
BANKR|Bankrupt Corp|G|N|Q|100|N|N
"""

OTHER_FIXTURE = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
MSFT|Microsoft Corporation Common Stock|N|MSFT|N|100|N|MSFT
BRK.B|Berkshire Hathaway Inc. New Common Stock|N|BRK.B|N|40|N|BRK.B
XLE|SPDR Select Sector Fund - Energy Select Sector|P|XLE|Y|100|N|XLE
WARR|Example Corp Warrant|N|WARR|N|100|N|WARR
"""


@pytest.fixture(autouse=True)
def _clean_listing_cache():
    init_db()
    session_keys = [
        lm.CACHE_KEY_SNAPSHOT,
        lm.CACHE_KEY_REVISION,
        "universe:sp500",
    ]
    cache = Cache()
    for key in session_keys:
        data = cache.get(key)
        if data is not None:
            cache.set(key, data, ttl_seconds=0.001)
    _get_universe_cached.cache_clear()
    yield
    _get_universe_cached.cache_clear()


def _seed_listing_snapshot(symbols: list[str]) -> str:
    cache = Cache()
    snap = {
        "symbols": sorted(set(symbols)),
        "updated_at": "2026-06-15T12:00:00Z",
        "source": "test-fixture",
        "record_count": len(set(symbols)),
    }
    cache.set(lm.CACHE_KEY_SNAPSHOT, snap, ttl_seconds=86400)
    cache.set(
        lm.CACHE_KEY_REVISION,
        {"revision": "test-rev-1", "updated_at": snap["updated_at"]},
        ttl_seconds=86400,
    )
    _get_universe_cached.cache_clear()
    return "test-rev-1"


def test_universe_is_sorted_and_unique():
    _seed_listing_snapshot(["AAPL", "MSFT", "GOOGL"])
    with patch("data.universe._load_sp500_from_cache", return_value=[]):
        symbols = get_universe("compounder")
    assert symbols == sorted(symbols)
    assert len(symbols) == len(set(symbols))


def test_symbol_aliases_are_applied():
    assert normalize_symbol("sq") == "XYZ"
    assert normalize_symbol("FREY") == "TE"
    assert TICKER_ALIASES["SQ"] == "XYZ"


def test_stale_symbols_are_excluded():
    _seed_listing_snapshot(list(STALE_OR_DELISTED) + ["AAPL"])
    with patch("data.universe._load_sp500_from_cache", return_value=[]):
        symbols = get_universe("penny")
    for stale in STALE_OR_DELISTED:
        assert stale not in symbols


def test_stock_buckets_exclude_sector_etfs():
    etf = sorted(SECTOR_ETFS)[0]
    _seed_listing_snapshot([etf, "AAPL"])
    with patch("data.universe._load_sp500_from_cache", return_value=[]):
        symbols = get_universe("compounder")
    assert etf not in symbols
    assert "AAPL" in symbols


def test_supported_class_share_symbol_is_preserved():
    assert normalize_symbol("BRK.B") == "BRK-B"
    _seed_listing_snapshot(["BRK-B", "AAPL"])
    with patch("data.universe._load_sp500_from_cache", return_value=[]):
        symbols = get_universe("compounder")
    assert "BRK-B" in symbols


def test_listing_master_filters_test_issues():
    records = lm.parse_listing_files(nasdaq_text=NASDAQ_FIXTURE, other_text=OTHER_FIXTURE)
    active = lm.active_equity_symbols(records)
    assert "TESTY" not in active


def test_listing_master_filters_etfs():
    records = lm.parse_listing_files(nasdaq_text=NASDAQ_FIXTURE, other_text=OTHER_FIXTURE)
    active = lm.active_equity_symbols(records)
    assert "SPY" not in active
    assert "XLE" not in active


def test_listing_master_filters_warrants_units_and_rights():
    records = lm.parse_listing_files(nasdaq_text=NASDAQ_FIXTURE, other_text=OTHER_FIXTURE)
    active = lm.active_equity_symbols(records)
    assert "AACBR" not in active
    assert "AACBU" not in active
    assert "WARR" not in active


def test_listing_master_filters_bad_financial_status():
    records = lm.parse_listing_files(nasdaq_text=NASDAQ_FIXTURE, other_text=OTHER_FIXTURE)
    active = lm.active_equity_symbols(records)
    assert "BANKR" not in active


def test_listing_master_keeps_supported_ordinary_equities():
    records = lm.parse_listing_files(nasdaq_text=NASDAQ_FIXTURE, other_text=OTHER_FIXTURE)
    active = lm.active_equity_symbols(records)
    assert "AAPL" in active
    assert "MSFT" in active
    assert "XYZ" in active
    assert "BRK-B" in active


def test_get_universe_uses_active_listing_intersection():
    _seed_listing_snapshot(["AAPL"])
    with patch("data.universe._load_sp500_from_cache", return_value=[]):
        symbols = get_universe("compounder")
    assert symbols == ["AAPL"]


def test_get_universe_falls_back_when_listing_master_missing():
    with patch("data.listing_master.get_active_listing_symbols", return_value=None):
        with patch("data.universe._load_sp500_from_cache", return_value=[]):
            symbols = get_universe("compounder")
    assert symbols
    assert "AAPL" in symbols
    assert all(s not in STALE_OR_DELISTED for s in symbols)
    assert all(s not in SECTOR_ETFS for s in symbols)


def test_get_universe_falls_back_when_refresh_fails():
    cache = Cache()
    cache.set(
        lm.CACHE_KEY_SNAPSHOT,
        {
            "symbols": ["AAPL"],
            "updated_at": "2026-06-01T00:00:00Z",
            "source": "stale",
            "record_count": 1,
        },
        ttl_seconds=86400,
    )
    with patch("data.listing_master._fetch_url", side_effect=TimeoutError("network down")):
        result = lm.refresh_listing_master(force=True)
    assert result["status"] == "stale"
    assert result["symbol_count"] == 1


def test_revision_change_invalidates_lru_cache():
    _seed_listing_snapshot(["AAPL"])
    with patch("data.universe._load_sp500_from_cache", return_value=[]):
        first = get_universe("compounder")
    cache = Cache()
    cache.set(
        lm.CACHE_KEY_REVISION,
        {"revision": "test-rev-2", "updated_at": "2026-06-16T00:00:00Z"},
        ttl_seconds=86400,
    )
    cache.set(
        lm.CACHE_KEY_SNAPSHOT,
        {"symbols": ["AAPL", "MSFT"], "updated_at": "2026-06-16T00:00:00Z", "source": "test", "record_count": 2},
        ttl_seconds=86400,
    )
    with patch("data.universe._load_sp500_from_cache", return_value=[]):
        second = get_universe("compounder")
    assert "MSFT" in second
    assert len(second) >= len(first)


def test_theme_membership_preserves_multi_theme_symbols():
    assert "APLD" in SYMBOL_THEMES
    assert len(SYMBOL_THEMES["APLD"]) >= 2
    assert "SPCE" in SYMBOL_THEMES
    assert len(SYMBOL_THEMES["SPCE"]) >= 2


def test_penny_discovery_seeds_exclude_sector_etfs_from_large_cap():
    overlap = set(PENNY_DISCOVERY_SEEDS) & SECTOR_ETFS
    assert not overlap
    overlap_large = set(LARGE_CAP_SEEDS) & SECTOR_ETFS
    assert not overlap_large


def test_get_universe_revision_uses_listing_master():
    _seed_listing_snapshot(["AAPL"])
    assert get_universe_revision() == "test-rev-1"


def test_cap_universe_for_scan_avoids_alphabetical_prefix_bias():
    symbols = [f"S{i:03d}" for i in range(200)]
    capped = cap_universe_for_scan(symbols, 50, revision="rev-a")
    assert len(capped) == 50
    assert capped == sorted(capped)
    assert capped != sorted(symbols)[:50]
    assert cap_universe_for_scan(symbols, 50, revision="rev-a") == capped
    assert cap_universe_for_scan(symbols, 50, revision="rev-b") != capped


def test_cap_universe_for_scan_passthrough_when_unlimited():
    symbols = ["ZZZ", "AAA", "MMM"]
    assert cap_universe_for_scan(symbols, 0) == symbols
    assert cap_universe_for_scan(symbols, 10) == symbols


def test_penny_seeds_exclude_known_stale_and_are_normalized():
    for stale in ("WIRE", "BBBY", "BYND", "SAVA", "MARK", "CAN", "ML"):
        assert stale in STALE_OR_DELISTED
        assert stale not in PENNY_DISCOVERY_SEEDS
    assert all(normalize_symbol(s) == s for s in PENNY_DISCOVERY_SEEDS)
    assert not (set(PENNY_DISCOVERY_SEEDS) & STALE_OR_DELISTED)
