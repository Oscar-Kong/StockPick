"""Finnhub API — earnings calendar and company news."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import requests

from config import FINNHUB_API_KEY
from data.cache import Cache

logger = logging.getLogger(__name__)

BASE = "https://finnhub.io/api/v1"
CACHE_TTL = 3600

RED_FLAG_KEYWORDS = {
    "dilution": ["offering", "secondary offering", "atm offering", "shelf registration", "dilution"],
    "legal": ["lawsuit", "sec investigation", "subpoena", "fraud", "class action"],
    "earnings": ["earnings", "eps", "guidance", "beat", "miss", "quarterly results"],
    "ma": ["merger", "acquisition", "buyout", "takeover"],
}


class FinnhubClient:
    def __init__(self, api_key: str | None = None, cache: Cache | None = None):
        self.api_key = api_key or FINNHUB_API_KEY
        self.cache = cache or Cache()

    def _get(self, path: str, params: dict | None = None) -> dict | list | None:
        if not self.api_key:
            return None
        params = dict(params or {})
        params["token"] = self.api_key
        try:
            r = requests.get(f"{BASE}{path}", params=params, timeout=12)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning("Finnhub %s failed: %s", path, exc)
            return None

    def get_quote(self, symbol: str) -> dict[str, Any]:
        """Latest quote — primary price source when PRIMARY_PRICE_SOURCE=finnhub."""
        sym = symbol.upper()
        data = self._get("/quote", {"symbol": sym})
        if not isinstance(data, dict) or data.get("c") is None:
            return {}
        price = float(data["c"])
        return {
            "symbol": sym,
            "currentPrice": price,
            "price": price,
            "open": data.get("o"),
            "high": data.get("h"),
            "low": data.get("l"),
            "previousClose": data.get("pc"),
            "source": "finnhub",
        }

    def get_earnings(self, symbol: str) -> dict[str, Any]:
        cached = self.cache.get(f"finnhub:earnings:{symbol.upper()}")
        if cached:
            return cached

        result: dict[str, Any] = {
            "earnings_date": None,
            "days_until": None,
            "earnings_soon": False,
            "source": "finnhub",
        }

        today = date.today()
        end = today + timedelta(days=90)
        data = self._get(
            "/calendar/earnings",
            {"from": today.isoformat(), "to": end.isoformat(), "symbol": symbol.upper()},
        )
        if isinstance(data, dict) and data.get("earningsCalendar"):
            rows = data["earningsCalendar"]
            sym_rows = [r for r in rows if r.get("symbol", "").upper() == symbol.upper()]
            if sym_rows:
                row = sorted(sym_rows, key=lambda x: x.get("date", ""))[0]
                ed = row.get("date")
                if ed:
                    d = datetime.strptime(ed[:10], "%Y-%m-%d").date()
                    days = (d - today).days
                    result["earnings_date"] = d.isoformat()
                    result["days_until"] = days
                    result["earnings_soon"] = 0 <= days <= 7

        self.cache.set(f"finnhub:earnings:{symbol.upper()}", result, CACHE_TTL)
        return result

    def get_company_news(self, symbol: str, days: int = 14) -> list[dict]:
        cached = self.cache.get(f"finnhub:news:{symbol.upper()}")
        if cached:
            return cached

        if not self.api_key:
            return []

        end = date.today()
        start = end - timedelta(days=days)
        data = self._get(
            "/company-news",
            {"symbol": symbol.upper(), "from": start.isoformat(), "to": end.isoformat()},
        )
        if not isinstance(data, list):
            return []

        articles = []
        for item in data[:30]:
            headline = item.get("headline", "") or ""
            summary = item.get("summary", "") or ""
            text = f"{headline} {summary}".lower()
            category = _categorize_news(text)
            articles.append(
                {
                    "headline": headline,
                    "summary": summary,
                    "datetime": item.get("datetime"),
                    "url": item.get("url"),
                    "category": category,
                    "sentiment_score": _headline_sentiment(text),
                }
            )

        self.cache.set(f"finnhub:news:{symbol.upper()}", articles, CACHE_TTL)
        return articles

    def news_summary(self, symbol: str) -> dict[str, Any]:
        articles = self.get_company_news(symbol)
        if not articles:
            return {"score": 50.0, "categories": {}, "red_flags": [], "headlines": []}

        scores = [a["sentiment_score"] for a in articles]
        cats: dict[str, int] = {}
        red_flags: list[str] = []
        for a in articles:
            cats[a["category"]] = cats.get(a["category"], 0) + 1
            if a["category"] == "dilution":
                red_flags.append(a["headline"][:120])
            if a["category"] == "legal":
                red_flags.append(a["headline"][:120])

        return {
            "score": sum(scores) / len(scores),
            "categories": cats,
            "red_flags": red_flags[:5],
            "headlines": [a["headline"] for a in articles[:5]],
        }


def _categorize_news(text: str) -> str:
    for cat, keys in RED_FLAG_KEYWORDS.items():
        if any(k in text for k in keys):
            return cat
    return "general"


def _headline_sentiment(text: str) -> float:
    pos = {"beat", "surge", "soar", "upgrade", "buy", "growth", "record", "strong"}
    neg = {"miss", "fall", "drop", "downgrade", "sell", "weak", "offering", "lawsuit", "cut"}
    p = sum(1 for w in pos if w in text)
    n = sum(1 for w in neg if w in text)
    if p + n == 0:
        return 50.0
    return max(0.0, min(100.0, 50 + (p - n) / (p + n) * 50))
