"""Financial Modeling Prep API client (stable endpoints)."""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import FMP_API_KEY
from data.cache import Cache

logger = logging.getLogger(__name__)

# New FMP keys only get /stable/* — legacy /api/v3 returns 403 "Legacy Endpoint".
BASE = "https://financialmodelingprep.com/stable"
CACHE_TTL = 86400


def _redact_secrets(message: str) -> str:
    """Strip API keys from log lines (requests embed apikey= in error URLs)."""
    import re

    return re.sub(r"(apikey=)[^&\s\"']+", r"\1***", message, flags=re.IGNORECASE)


def _response_body(response: Any) -> str:
    try:
        return str(getattr(response, "text", "") or "")
    except Exception:
        return ""


def _is_legacy_endpoint_block(response: Any) -> bool:
    body = _response_body(response)
    return "Legacy Endpoint" in body or "legacy endpoints" in body.lower()


class FMPClient:
    # Process-wide: after a real auth/tier 403, skip FMP for remaining calls.
    # Legacy-endpoint 403s do not trip this — those mean the URL is wrong.
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

    def _get(self, endpoint: str, params: dict | None = None) -> Any:
        if not self.api_key or FMPClient._access_denied:
            return None
        params = dict(params or {})
        params["apikey"] = self.api_key
        path = endpoint.lstrip("/")
        url = f"{BASE}/{path}"
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else None
            if status == 403 and _is_legacy_endpoint_block(response):
                logger.warning(
                    "FMP legacy endpoint rejected for %s — use /stable instead",
                    path,
                )
            elif status == 403:
                FMPClient._access_denied = True
                logger.warning(
                    "FMP access denied (403) — disabling FMP for this process; using yfinance fallback"
                )
            else:
                logger.warning("FMP %s failed: %s", path, _redact_secrets(str(exc)))
            return None
        except Exception as exc:
            msg = str(exc)
            if "403" in msg and "Legacy Endpoint" in msg:
                logger.warning(
                    "FMP legacy endpoint rejected for %s — use /stable instead",
                    path,
                )
            elif "403" in msg:
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

        data = self._get("profile", {"symbol": symbol.upper()})
        if not data or not isinstance(data, list):
            return {}

        row = data[0]
        profile = {
            "symbol": row.get("symbol"),
            "name": row.get("companyName"),
            "sector": row.get("sector"),
            "industry": row.get("industry"),
            "marketCap": row.get("marketCap") if row.get("marketCap") is not None else row.get("mktCap"),
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

        data = self._get("ratios-ttm", {"symbol": symbol.upper()})
        if not data or not isinstance(data, list):
            return {}

        row = data[0]
        # Stable field names differ from legacy /api/v3/ratios-ttm.
        ratios = {
            "pe_ratio": row.get("priceToEarningsRatioTTM", row.get("peRatioTTM")),
            "peg_ratio": row.get("priceToEarningsGrowthRatioTTM", row.get("pegRatioTTM")),
            "price_to_book": row.get("priceToBookRatioTTM"),
            "roe": row.get("returnOnEquityTTM"),
            "profit_margin": row.get("netProfitMarginTTM"),
            "operating_margin": row.get("operatingProfitMarginTTM"),
            "debt_to_equity": row.get("debtToEquityRatioTTM", row.get("debtEquityRatioTTM")),
            "current_ratio": row.get("currentRatioTTM"),
            "revenue_growth": None,
        }
        # ROE lives on key-metrics-ttm in the stable API.
        if ratios["roe"] is None:
            metrics = self._get("key-metrics-ttm", {"symbol": symbol.upper()})
            if isinstance(metrics, list) and metrics:
                ratios["roe"] = metrics[0].get("returnOnEquityTTM")
        self.cache.set(f"fmp:ratios:{symbol.upper()}", ratios, CACHE_TTL)
        return ratios

    def get_fundamentals_bundle(self, symbol: str) -> dict[str, Any]:
        profile = self.get_profile(symbol)
        ratios = self.get_ratios(symbol)
        return {**profile, **ratios, "source": "fmp"}

    def get_historical_eod(self, symbol: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        """Daily OHLCV bars newest-first from stable historical-price-eod/full."""
        data = self._get("historical-price-eod/full", {"symbol": symbol.upper()})
        if not isinstance(data, list):
            return []
        rows = [r for r in data if isinstance(r, dict) and r.get("date") is not None]
        if limit is not None and limit > 0:
            return rows[:limit]
        return rows

    def screener(
        self,
        market_cap_more_than: int | None = None,
        price_more_than: float | None = None,
        price_lower_than: float | None = None,
        volume_more_than: int | None = None,
        limit: int = 100,
        sector: str | None = None,
    ) -> list[str]:
        """Return symbols matching basic filters (stable company-screener)."""
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
        if sector:
            params["sector"] = sector

        data = self._get("company-screener", params)
        if not isinstance(data, list):
            return []
        return [r.get("symbol", "").upper() for r in data if r.get("symbol")]
