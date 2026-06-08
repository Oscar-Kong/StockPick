"""Sentiment scoring — Finnhub primary news; NewsAPI dev-only."""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import (
    FINNHUB_API_KEY,
    NEWSAPI_ENABLED,
    NEWSAPI_KEY,
    PRIMARY_NEWS_SOURCE,
)

logger = logging.getLogger(__name__)

POSITIVE_WORDS = {"buy", "bull", "bullish", "moon", "breakout", "long", "calls", "up", "growth", "strong"}
NEGATIVE_WORDS = {"sell", "bear", "bearish", "short", "puts", "down", "weak", "crash", "dump", "overvalued"}


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _lexicon_score(text: str) -> float:
    words = text.lower().split()
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    if pos + neg == 0:
        return 50.0
    return _clamp(50 + (pos - neg) / (pos + neg) * 50)


def fetch_stocktwits_sentiment(symbol: str) -> float:
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    try:
        response = requests.get(url, params={"limit": 30}, timeout=10)
        response.raise_for_status()
        messages = response.json().get("messages", [])
        if not messages:
            return 50.0

        scores = []
        for msg in messages:
            body = msg.get("body", "")
            sentiment_obj = msg.get("entities", {}).get("sentiment", {})
            if sentiment_obj and sentiment_obj.get("basic"):
                basic = sentiment_obj["basic"]
                if basic == "Bullish":
                    scores.append(75.0)
                elif basic == "Bearish":
                    scores.append(25.0)
                else:
                    scores.append(_lexicon_score(body))
            else:
                scores.append(_lexicon_score(body))
        return sum(scores) / len(scores)
    except Exception as exc:
        logger.warning("StockTwits failed for %s: %s", symbol, exc)
        return 50.0


def fetch_news_sentiment(symbol: str) -> float:
    """NewsAPI — only when explicitly enabled (dev/test licensing)."""
    if not NEWSAPI_ENABLED or not NEWSAPI_KEY:
        return 50.0

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": symbol,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 20,
        "apiKey": NEWSAPI_KEY,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        if not articles:
            return 50.0
        scores = []
        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '')}"
            scores.append(_lexicon_score(text))
        return sum(scores) / len(scores)
    except Exception as exc:
        logger.warning("NewsAPI failed for %s: %s", symbol, exc)
        return 50.0


def fetch_finnhub_sentiment(symbol: str) -> dict[str, Any]:
    if not FINNHUB_API_KEY:
        return {"score": 50.0, "categories": {}, "red_flags": []}
    from data.finnhub_client import FinnhubClient

    return FinnhubClient().news_summary(symbol)


def sentiment_polarity_scores(symbol: str) -> dict[str, float]:
    """Positive / negative buzz scores (0–100) from StockTwits messages."""
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    combined = 50.0
    positive = 50.0
    negative = 50.0
    try:
        response = requests.get(url, params={"limit": 30}, timeout=10)
        response.raise_for_status()
        messages = response.json().get("messages", [])
        if not messages:
            return {"combined": 50.0, "positive": 50.0, "negative": 50.0}

        pos = neg = neu = 0
        for msg in messages:
            basic = (msg.get("entities", {}).get("sentiment") or {}).get("basic")
            if basic == "Bullish":
                pos += 1
            elif basic == "Bearish":
                neg += 1
            else:
                body = msg.get("body", "")
                lex = _lexicon_score(body)
                if lex >= 60:
                    pos += 1
                elif lex <= 40:
                    neg += 1
                else:
                    neu += 1
        total = pos + neg + neu or 1
        pos_share = pos / total
        neg_share = neg / total
        positive = _clamp(40 + pos_share * 60)
        negative = _clamp(40 + (1 - neg_share) * 60)
        combined = fetch_stocktwits_sentiment(symbol)
    except Exception as exc:
        logger.debug("Polarity fetch failed %s: %s", symbol, exc)
    return {"combined": combined, "positive": positive, "negative": negative}


def combined_sentiment_score(symbol: str, include_news: bool = False) -> dict[str, Any]:
    stocktwits = fetch_stocktwits_sentiment(symbol)
    if not include_news:
        return {"score": stocktwits, "stocktwits": stocktwits, "news": 50.0}

    news_score = 50.0
    fh_meta: dict[str, Any] = {"categories": {}, "red_flags": []}

    if PRIMARY_NEWS_SOURCE == "finnhub" and FINNHUB_API_KEY:
        fh = fetch_finnhub_sentiment(symbol)
        news_score = fh["score"]
        fh_meta = fh
    elif PRIMARY_NEWS_SOURCE == "newsapi" and NEWSAPI_ENABLED:
        news_score = fetch_news_sentiment(symbol)
    elif FINNHUB_API_KEY:
        fh = fetch_finnhub_sentiment(symbol)
        news_score = fh["score"]
        fh_meta = fh

    score = stocktwits * 0.4 + news_score * 0.6
    return {
        "score": score,
        "stocktwits": stocktwits,
        "news": news_score,
        "categories": fh_meta.get("categories", {}),
        "red_flags": fh_meta.get("red_flags", []),
    }
