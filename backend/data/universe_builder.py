"""Dynamic universe filtering using bulk price data."""
from __future__ import annotations

from config import (
    COMPOUNDER_MARKET_CAP_MIN,
    MEDIUM_MARKET_CAP_MAX,
    MEDIUM_MARKET_CAP_MIN,
    MEDIUM_MIN_DOLLAR_VOLUME_20D,
    MEDIUM_MIN_VOLUME,
    MEDIUM_PRICE_MAX,
    MEDIUM_PRICE_MIN,
    PENNY_MARKET_CAP_MAX,
    PENNY_MARKET_CAP_MIN,
    PENNY_MIN_DOLLAR_VOLUME_20D,
    PENNY_MIN_VOLUME,
    PENNY_PRICE_MAX,
    PENNY_PRICE_MIN,
)
from data.universe import get_universe
from models.schemas import Bucket


def filter_universe_by_price(
    bucket: Bucket,
    bulk_hist: dict,
    bulk_info: dict | None = None,
) -> list[str]:
    """Stage A: keep symbols matching bucket price/volume heuristics from bulk data."""
    universe = get_universe(bucket.value)
    passed: list[str] = []

    for symbol in universe:
        hist = bulk_hist.get(symbol.upper())
        if hist is None or hist.empty:
            continue
        price = float(hist["close"].iloc[-1])
        tail = hist.tail(min(20, len(hist)))
        avg_vol = float(tail["volume"].mean()) if len(tail) else 0.0
        dollar_vol = float((tail["close"] * tail["volume"]).mean()) if len(tail) else 0.0

        info = (bulk_info or {}).get(symbol.upper(), {})
        mcap = info.get("marketCap")

        if bucket == Bucket.penny:
            if not (PENNY_PRICE_MIN <= price <= PENNY_PRICE_MAX):
                continue
            if avg_vol < PENNY_MIN_VOLUME or dollar_vol < PENNY_MIN_DOLLAR_VOLUME_20D:
                continue
            if mcap and (mcap < PENNY_MARKET_CAP_MIN or mcap > PENNY_MARKET_CAP_MAX):
                continue
        elif bucket == Bucket.medium:
            if not (MEDIUM_PRICE_MIN <= price <= MEDIUM_PRICE_MAX):
                continue
            if avg_vol < MEDIUM_MIN_VOLUME or dollar_vol < MEDIUM_MIN_DOLLAR_VOLUME_20D:
                continue
            if mcap and (mcap < MEDIUM_MARKET_CAP_MIN or mcap > MEDIUM_MARKET_CAP_MAX):
                continue
        else:  # compounder
            if mcap and mcap < COMPOUNDER_MARKET_CAP_MIN:
                continue
            if price < 5 and not mcap:
                continue

        passed.append(symbol.upper())

    return passed
