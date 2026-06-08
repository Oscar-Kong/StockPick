"""Alpha Vantage client for fundamentals."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from config import ALPHA_VANTAGE_API_KEY
from data.cache import Cache

logger = logging.getLogger(__name__)


class AlphaVantageClient:
    BASE_URL = "https://www.alphavantage.co/query"
    # Keep requests quick for scan/analyze UX; API-side limits are still handled by "Note" responses.
    MIN_INTERVAL = 0.5

    def __init__(self, api_key: str | None = None, cache: Cache | None = None):
        self.api_key = api_key or ALPHA_VANTAGE_API_KEY
        self.cache = cache or Cache()
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self.MIN_INTERVAL:
            time.sleep(self.MIN_INTERVAL - elapsed)

    def get_overview(self, symbol: str) -> dict[str, Any]:
        cached = self.cache.get_fundamentals_cache(symbol)
        if cached:
            return cached

        if not self.api_key:
            return {}

        self._rate_limit()
        params = {"function": "OVERVIEW", "symbol": symbol, "apikey": self.api_key}
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            self._last_request = time.time()

            if "Error Message" in data or "Note" in data:
                logger.warning("Alpha Vantage issue for %s: %s", symbol, data)
                return {}

            fundamentals = {
                "symbol": data.get("Symbol", symbol),
                "name": data.get("Name", ""),
                "sector": data.get("Sector", ""),
                "industry": data.get("Industry", ""),
                "market_cap": _safe_float(data.get("MarketCapitalization")),
                "pe_ratio": _safe_float(data.get("PERatio")),
                "peg_ratio": _safe_float(data.get("PEGRatio")),
                "eps": _safe_float(data.get("EPS")),
                "revenue_ttm": _safe_float(data.get("RevenueTTM")),
                "profit_margin": _safe_float(data.get("ProfitMargin")),
                "operating_margin": _safe_float(data.get("OperatingMarginTTM")),
                "return_on_equity": _safe_float(data.get("ReturnOnEquityTTM")),
                "return_on_assets": _safe_float(data.get("ReturnOnAssetsTTM")),
                "debt_to_equity": _safe_float(data.get("DebtToEquity")),
                "dividend_yield": _safe_float(data.get("DividendYield")),
                "beta": _safe_float(data.get("Beta")),
                "52_week_high": _safe_float(data.get("52WeekHigh")),
                "52_week_low": _safe_float(data.get("52WeekLow")),
                "analyst_target": _safe_float(data.get("AnalystTargetPrice")),
                "description": data.get("Description", ""),
            }
            self.cache.set_fundamentals_cache(symbol, fundamentals)
            return fundamentals
        except Exception as exc:
            logger.warning("Alpha Vantage fetch failed for %s: %s", symbol, exc)
            return {}


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "None", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
