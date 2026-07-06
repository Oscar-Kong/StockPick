"""Dynamic universe filtering using bulk price data."""
from __future__ import annotations

from config import (
    COMPOUNDER_MARKET_CAP_MIN,
    PENNY_MARKET_CAP_MAX,
    PENNY_MARKET_CAP_MIN,
    PENNY_MIN_DOLLAR_VOLUME_20D,
    PENNY_MIN_VOLUME,
    PENNY_PRICE_MAX,
    PENNY_PRICE_MIN,
)
from data.universe import get_universe
from models.schemas import Bucket


def check_bucket_eligibility(
    bucket: Bucket,
    hist: object,
    info: dict | None = None,
) -> tuple[bool, str | None]:
    """Return whether symbol passes bucket price/volume heuristics and a rejection reason."""
    import pandas as pd

    if hist is None or not isinstance(hist, pd.DataFrame) or hist.empty:
        return False, "missing_history"

    info = info or {}
    price = float(hist["close"].iloc[-1])
    tail = hist.tail(min(20, len(hist)))
    avg_vol = float(tail["volume"].mean()) if len(tail) else 0.0
    dollar_vol = float((tail["close"] * tail["volume"]).mean()) if len(tail) else 0.0
    mcap = info.get("marketCap")

    if bucket == Bucket.penny:
        if not (PENNY_PRICE_MIN <= price <= PENNY_PRICE_MAX):
            return False, "price_out_of_range"
        if avg_vol < PENNY_MIN_VOLUME or dollar_vol < PENNY_MIN_DOLLAR_VOLUME_20D:
            return False, "insufficient_liquidity"
        if mcap and (mcap < PENNY_MARKET_CAP_MIN or mcap > PENNY_MARKET_CAP_MAX):
            return False, "market_cap_out_of_range"
    else:  # compounder
        if mcap and mcap < COMPOUNDER_MARKET_CAP_MIN:
            return False, "market_cap_below_minimum"
        if price < 5 and not mcap:
            return False, "price_below_minimum_without_mcap"

    return True, None


def filter_universe_by_price(
    bucket: Bucket,
    bulk_hist: dict,
    bulk_info: dict | None = None,
) -> list[str]:
    """Stage A eligibility: keep symbols matching bucket price/volume heuristics from bulk data."""
    universe = get_universe(bucket.value)
    passed: list[str] = []

    for symbol in universe:
        sym = symbol.upper()
        hist = bulk_hist.get(sym)
        info = (bulk_info or {}).get(sym, {})
        ok, _reason = check_bucket_eligibility(bucket, hist, info)
        if ok:
            passed.append(sym)

    return passed
