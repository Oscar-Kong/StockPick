"""Nasdaq Data Link client — reference/batch datasets (not live quote primary)."""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import NASDAQ_DATA_LINK_API_KEY, QUANDL_API_KEY
from data.cache import Cache

logger = logging.getLogger(__name__)

BASE = "https://data.nasdaq.com/api/v3"
CACHE_TTL = 86400 * 7


class QuandlClient:
    """Fetch supplementary datasets when NASDAQ_DATA_LINK_API_KEY is configured."""

    def __init__(self, api_key: str | None = None, cache: Cache | None = None):
        self.api_key = api_key or NASDAQ_DATA_LINK_API_KEY or QUANDL_API_KEY
        self.cache = cache or Cache()

    def _get(self, dataset: str, params: dict | None = None) -> dict | list | None:
        if not self.api_key:
            return None
        params = dict(params or {})
        params["api_key"] = self.api_key
        try:
            r = requests.get(f"{BASE}/datasets/{dataset}.json", params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning("Quandl %s failed: %s", dataset, exc)
            return None

    def get_latest_value(self, dataset: str, column: int = 1) -> float | None:
        """Return latest numeric value from a Quandl dataset."""
        cache_key = f"quandl:{dataset}:latest"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached.get("value")

        data = self._get(dataset, {"rows": 1})
        if not data or "dataset_data" not in data:
            return None

        rows = data["dataset_data"].get("data") or []
        if not rows:
            return None

        try:
            val = float(rows[0][column])
            self.cache.set(cache_key, {"value": val}, CACHE_TTL)
            return val
        except (IndexError, TypeError, ValueError):
            return None

    def get_macro_snapshot(self) -> dict[str, Any]:
        """Return macro indicators when key is set; empty dict otherwise."""
        if not self.api_key:
            return {"configured": False, "message": "QUANDL_API_KEY not set"}

        # WIKI/SPY as market proxy; FRED via Quandl if available
        spy = self.get_latest_value("WIKI/SPY")
        return {
            "configured": True,
            "spy_reference": spy,
            "source": "quandl",
        }
