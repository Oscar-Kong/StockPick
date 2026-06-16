"""Financial Modeling Prep API client."""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import FMP_API_KEY
from data.cache import Cache

logger = logging.getLogger(__name__)

BASE = "https://financialmodelingprep.com/api/v3"
CACHE_TTL = 86400


def _redact_secrets(message: str) -> str:
    """Strip API keys from log lines (requests embed apikey= in error URLs)."""
    import re

    return re.sub(r"(apikey=)[^&\s\"']+", r"\1***", message, flags=re.IGNORECASE)


class FMPClient:
    # Process-wide: after a 403 (tier/key block), skip FMP for remaining calls.
    _access_denied: bool = False

    def __init__(self, api_key: str | None = None, cache: Cache | None = None):
        self.api_key = api_key or FMP_API_KEY
        self.cache = cache or Cache()

    @classmethod
    def is_disabled(cls) -> bool:
        return cls._access_denied

    @classmethod
    def reset_access_denied(cls) -> None:
        """Test helper — restore FMP after circuit-breaker trips."""
        cls._access_denied = False

    def _get(self, path: str, params: dict | None = None) -> Any:
        if not self.api_key or FMPClient._access_denied:
            return None
        params = dict(params or {})
        params["apikey"] = self.api_key
        try:
            r = requests.get(f"{BASE}{path}", params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 403:
                FMPClient._access_denied = True
                logger.warning(
                    "FMP access denied (403) — disabling FMP for this process; using yfinance fallback"
                )
            else:
                logger.warning("FMP %s failed: %s", path, _redact_secrets(str(exc)))
            return None
        except Exception as exc:
            msg = str(exc)
            if "403" in msg:
                FMPClient._access_denied = True
                logger.warning(
                    "FMP access denied (403) — disabling FMP for this process; using yfinance fallback"
                )
            else:
                logger.warning("FMP %s failed: %s", path, _redact_secrets(msg))
            return None

    def get_profile(self, symbol: str) -> dict[str, Any]:
        cached = self.cache.get(f"fmp:profile:{symbol.upper()}")
        if cached:
            return cached

        data = self._get(f"/profile/{symbol.upper()}")
        if not data or not isinstance(data, list):
            return {}

        row = data[0]
        profile = {
            "symbol": row.get("symbol"),
            "name": row.get("companyName"),
            "sector": row.get("sector"),
            "industry": row.get("industry"),
            "marketCap": row.get("mktCap"),
            "beta": row.get("beta"),
            "pe_ratio": row.get("pe"),
            "price": row.get("price"),
        }
        self.cache.set(f"fmp:profile:{symbol.upper()}", profile, CACHE_TTL)
        return profile

    def get_ratios(self, symbol: str) -> dict[str, Any]:
        cached = self.cache.get(f"fmp:ratios:{symbol.upper()}")
        if cached:
            return cached

        data = self._get(f"/ratios-ttm/{symbol.upper()}")
        if not data or not isinstance(data, list):
            return {}

        row = data[0]
        ratios = {
            "pe_ratio": row.get("peRatioTTM"),
            "peg_ratio": row.get("pegRatioTTM"),
            "price_to_book": row.get("priceToBookRatioTTM"),
            "roe": row.get("returnOnEquityTTM"),
            "profit_margin": row.get("netProfitMarginTTM"),
            "operating_margin": row.get("operatingProfitMarginTTM"),
            "debt_to_equity": row.get("debtEquityRatioTTM"),
            "current_ratio": row.get("currentRatioTTM"),
            "revenue_growth": None,
        }
        self.cache.set(f"fmp:ratios:{symbol.upper()}", ratios, CACHE_TTL)
        return ratios

    def get_fundamentals_bundle(self, symbol: str) -> dict[str, Any]:
        profile = self.get_profile(symbol)
        ratios = self.get_ratios(symbol)
        return {**profile, **ratios, "source": "fmp"}

    def screener(
        self,
        market_cap_more_than: int | None = None,
        price_more_than: float | None = None,
        price_lower_than: float | None = None,
        volume_more_than: int | None = None,
        limit: int = 100,
    ) -> list[str]:
        """Return symbols matching basic filters."""
        if not self.api_key:
            return []

        params: dict[str, Any] = {"limit": limit, "isActivelyTrading": "true"}
        if market_cap_more_than:
            params["marketCapMoreThan"] = market_cap_more_than
        if price_more_than:
            params["priceMoreThan"] = price_more_than
        if price_lower_than:
            params["priceLowerThan"] = price_lower_than
        if volume_more_than:
            params["volumeMoreThan"] = volume_more_than

        data = self._get("/stock-screener", params)
        if not isinstance(data, list):
            return []
        return [r.get("symbol", "").upper() for r in data if r.get("symbol")]
