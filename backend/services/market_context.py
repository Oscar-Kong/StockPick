"""Attach earnings, valuation, and news context to screener metrics."""
from __future__ import annotations

from typing import Any

from config import FINNHUB_API_KEY
from data.earnings import get_next_earnings_date
from data.finnhub_client import FinnhubClient
from data.historical_store import HistoricalStore
from data.reconciler import DataReconciler
from models.schemas import Bucket
from scoring.valuation import valuation_warnings


def enrich_metrics(
    symbol: str,
    info: dict,
    fundamentals: dict,
    metrics: dict[str, Any],
    bucket: Bucket,
    *,
    use_reconciler: bool = True,
    allow_openbb_fetch: bool | None = None,
) -> dict[str, Any]:
    metrics = dict(metrics)
    sym = symbol.upper()

    if use_reconciler:
        info, fundamentals, rec = DataReconciler().get_canonical_fundamentals(sym)
        metrics["data_quality_score"] = rec.quality_score
        metrics["data_quality_flags"] = rec.flags
        metrics["reconcile_audit"] = rec.source_audit
        HistoricalStore().save_fundamentals(
            sym,
            {"info": info, "fundamentals": fundamentals},
            source="reconciled",
            quality_score=rec.quality_score,
        )
        for flag in rec.flags:
            HistoricalStore().add_quality_flag(sym, "reconcile", flag)

    earnings: dict[str, Any]
    if FINNHUB_API_KEY:
        earnings = FinnhubClient().get_earnings(sym)
        if not earnings.get("earnings_date"):
            earnings = get_next_earnings_date(sym)
    else:
        earnings = get_next_earnings_date(sym)

    metrics["earnings_date"] = earnings.get("earnings_date")
    metrics["days_until_earnings"] = earnings.get("days_until")
    metrics["earnings_soon"] = earnings.get("earnings_soon", False)

    news_data: dict[str, Any] = {"score": 50.0, "categories": {}, "red_flags": [], "headlines": []}
    if FINNHUB_API_KEY:
        news_data = FinnhubClient().news_summary(sym)
    metrics["news_score"] = news_data.get("score", 50.0)
    metrics["news_categories"] = news_data.get("categories", {})
    metrics["news_red_flags"] = news_data.get("red_flags", [])
    metrics["news_headlines"] = news_data.get("headlines", [])

    warnings: list[str] = []
    if bucket in (Bucket.medium, Bucket.compounder):
        warnings = valuation_warnings(info, fundamentals)
    elif earnings.get("earnings_soon"):
        warnings = ["Earnings within 7 days — high volatility risk"]

    for flag in news_data.get("red_flags", [])[:2]:
        if "offering" in flag.lower() or "dilution" in flag.lower():
            warnings.append(f"News: possible dilution — {flag[:80]}")
        elif "lawsuit" in flag.lower() or "sec" in flag.lower():
            warnings.append(f"News: legal risk — {flag[:80]}")

    metrics["valuation_warnings"] = list(dict.fromkeys(warnings))
    if warnings:
        metrics["valuation_flag"] = True

    try:
        from services.openbb_integration import apply_openbb_to_metrics

        metrics, warnings = apply_openbb_to_metrics(
            sym,
            metrics,
            metrics["valuation_warnings"],
            allow_fetch=allow_openbb_fetch,
        )
        metrics["valuation_warnings"] = warnings
        if warnings:
            metrics["valuation_flag"] = True
    except Exception as exc:
        import logging

        logging.getLogger(__name__).debug("OpenBB metrics enrichment skipped: %s", exc)

    return metrics
