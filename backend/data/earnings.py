"""Earnings calendar helpers via Finnhub."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from data.cache import Cache
from data.finnhub_client import FinnhubClient

logger = logging.getLogger(__name__)

EARNINGS_CACHE_TTL = 86400  # 24h


def get_next_earnings_date(symbol: str, cache: Cache | None = None) -> dict[str, Any]:
    """
    Returns { earnings_date, days_until, earnings_soon }.
    earnings_date is ISO string or None.
    """
    cache = cache or Cache()
    key = f"earnings:{symbol.upper()}"
    cached = cache.get(key)
    if cached:
        return cached

    result: dict[str, Any] = {
        "earnings_date": None,
        "days_until": None,
        "earnings_soon": False,
    }

    try:
        earnings = FinnhubClient(cache=cache).get_earnings(symbol.upper())
        earnings_date = earnings.get("earnings_date")
        if earnings_date:
            next_date = _to_date(earnings_date)
            if next_date:
                days = (next_date - date.today()).days
                result["earnings_date"] = next_date.isoformat()
                result["days_until"] = days
                result["earnings_soon"] = 0 <= days <= 7
    except Exception as exc:
        logger.warning("Earnings lookup failed for %s: %s", symbol, exc)

    cache.set(key, result, EARNINGS_CACHE_TTL)
    return result


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None
