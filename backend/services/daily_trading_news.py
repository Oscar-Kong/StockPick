"""News context classification — never auto-buy/sell on headlines alone."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NewsClassification:
  classification: str
  measurements: dict[str, Any] = field(default_factory=dict)
  rationale: str = ""


def classify_news_context(
  *,
  news_summary: dict | None,
  price: float,
  prev_close: float | None,
  momentum_score: float | None,
  gap_pct: float | None = None,
) -> NewsClassification:
  """Interpret news as context relative to price behavior."""
  summary = news_summary or {}
  sentiment = float(summary.get("score") or 50.0)
  categories = summary.get("categories") or {}
  red_flags = summary.get("red_flags") or []
  headlines = summary.get("headlines") or []

  gap = gap_pct
  if gap is None and prev_close and prev_close > 0:
    gap = (price - prev_close) / prev_close * 100

  measurements = {
    "news_sentiment_score": round(sentiment, 1),
    "headline_count": len(headlines),
    "red_flag_count": len(red_flags),
    "categories": dict(categories),
    "gap_pct": round(gap, 2) if gap is not None else None,
    "momentum_score": momentum_score,
  }

  positive_news = sentiment >= 60 or bool(categories.get("earnings")) or bool(categories.get("ma"))
  negative_news = sentiment <= 40 or bool(red_flags) or bool(categories.get("legal"))

  mom = momentum_score if momentum_score is not None else 50.0

  if positive_news and (gap is not None and gap >= 5) and mom < 55:
    return NewsClassification(
      classification="positive_news_priced_in",
      measurements=measurements,
      rationale="Positive catalyst followed by extended gap and weakening momentum",
    )

  if negative_news and mom >= 55 and (gap is None or gap > -3):
    return NewsClassification(
      classification="negative_news_absorbed",
      measurements=measurements,
      rationale="Negative headline with stabilizing price and technical confirmation present",
    )

  if (positive_news or negative_news) and abs(mom - 50) < 8:
    return NewsClassification(
      classification="headline_unconfirmed",
      measurements=measurements,
      rationale="Market response has not yet confirmed the headline interpretation",
    )

  return NewsClassification(
    classification="no_actionable_news_edge",
    measurements=measurements,
    rationale="News does not materially improve the setup",
  )
