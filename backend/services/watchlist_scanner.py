"""Scan user-provided symbols and add them to the watchlist."""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime
from typing import Literal

from config import (
    COMPOUNDER_MARKET_CAP_MIN,
    MEDIUM_PRICE_MAX,
    MEDIUM_PRICE_MIN,
    PENNY_PRICE_MAX,
)
from data import cache as cache_module
from data.candidate_builder import build_candidate
from data.price_service import PriceService
from models.schemas import Bucket, ScanOptions, StockResult
from screeners.compounder import CompounderScreener
from screeners.medium import MediumScreener
from screeners.penny import PennyScreener
from services.market_context import enrich_metrics
from services.symbol_parser import parse_symbols

logger = logging.getLogger(__name__)
_ANALYZE_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="watchlist-analyze")

BucketChoice = Bucket | Literal["auto"]

_SCREENERS = {
    Bucket.penny: PennyScreener,
    Bucket.medium: MediumScreener,
    Bucket.compounder: CompounderScreener,
}


def detect_bucket(price: float, market_cap: float | None) -> Bucket:
    if price > 0 and price <= PENNY_PRICE_MAX:
        return Bucket.penny
    if market_cap and market_cap >= COMPOUNDER_MARKET_CAP_MIN:
        if price >= MEDIUM_PRICE_MAX or price == 0:
            return Bucket.compounder
    if MEDIUM_PRICE_MIN <= price <= MEDIUM_PRICE_MAX:
        return Bucket.medium
    if market_cap and market_cap >= COMPOUNDER_MARKET_CAP_MIN:
        return Bucket.compounder
    if price > PENNY_PRICE_MAX and price < MEDIUM_PRICE_MIN:
        return Bucket.penny if price < 10 else Bucket.medium
    return Bucket.medium


def analyze_symbol(
    symbol: str,
    bucket_choice: BucketChoice = "auto",
) -> tuple[StockResult | None, str | None]:
    bucket: Bucket
    if bucket_choice == "auto":
        ps = PriceService()
        ctx = build_candidate(symbol, history_period="3mo", reconcile=True, price_service=ps)
        if ctx is None:
            return None, f"No market data found for {symbol}"

        price = ctx.price
        mcap = ctx.info.get("marketCap")
        bucket = detect_bucket(price, float(mcap) if mcap else None)
    else:
        bucket = bucket_choice

    screener = _SCREENERS[bucket]()
    try:
        ctx = screener.enrich(symbol)
        if ctx is None:
            return None, f"Could not load data for {symbol}"

        options = ScanOptions()
        passed_filter = screener.hard_filter(ctx, options)
        score, signals, risk, summary, metrics = screener.score(ctx)
        from scoring.data_quality import adjust_score_for_data_quality

        quality_score = ctx.info.get("_reconcile_quality")
        score = adjust_score_for_data_quality(score, quality_score)
        metrics = enrich_metrics(
            symbol,
            ctx.info,
            ctx.fundamentals,
            metrics,
            bucket,
            # Avoid slow/interactive OpenBB SEC backfills during watchlist add/import.
            allow_openbb_fetch=False,
        )
        try:
            from services.openbb_integration import apply_openbb_score_adjustment

            score = apply_openbb_score_adjustment(score, metrics)
        except Exception:
            pass

        if not passed_filter:
            summary = f"[Outside typical {bucket.value} filters] {summary}"
        if metrics.get("earnings_soon"):
            summary = f"[Earnings soon] {summary}"

        result = screener.to_result(ctx, round(score, 1), signals, risk, summary, metrics)
        return result, None
    except Exception as exc:
        logger.warning("Analyze failed for %s: %s", symbol, exc)
        return None, str(exc)


def _analyze_with_timeout(
    symbol: str,
    bucket_choice: BucketChoice,
    timeout_seconds: float | None,
) -> tuple[StockResult | None, str | None]:
    if not timeout_seconds or timeout_seconds <= 0:
        return analyze_symbol(symbol, bucket_choice)
    future = _ANALYZE_EXECUTOR.submit(analyze_symbol, symbol, bucket_choice)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeout:
        return None, f"Timed out analyzing {symbol.upper()}"


def _save_result_to_watchlist(result: StockResult, user_notes: str) -> dict:
    metrics = result.metrics or {}
    notes = user_notes
    if notes:
        notes = f"{notes} | {result.summary}"
    else:
        notes = result.summary

    return cache_module.add_to_watchlist(
        symbol=result.symbol,
        bucket=result.bucket.value,
        notes=notes,
        price=result.price,
        score=result.score,
        summary=result.summary,
        last_scanned_at=datetime.utcnow(),
        earnings_date=metrics.get("earnings_date"),
        days_until_earnings=metrics.get("days_until_earnings"),
        valuation_warnings=metrics.get("valuation_warnings", []),
    )


def import_to_watchlist(
    text: str,
    bucket_choice: BucketChoice = "auto",
    user_notes: str = "",
    *,
    include_reports: bool = False,
    max_symbols: int | None = None,
    per_symbol_timeout_seconds: float | None = 10.0,
) -> list[dict]:
    symbols = parse_symbols(text)
    if not symbols:
        return []
    if max_symbols and max_symbols > 0:
        symbols = symbols[:max_symbols]

    outcomes: list[dict] = []
    for symbol in symbols:
        result, error = _analyze_with_timeout(symbol, bucket_choice, per_symbol_timeout_seconds)
        if error or result is None:
            outcomes.append(
                {
                    "symbol": symbol.upper(),
                    "bucket": bucket_choice if bucket_choice != "auto" else "medium",
                    "price": None,
                    "score": None,
                    "summary": error or "Unknown error",
                    "notes": user_notes,
                    "added": False,
                    "error": error,
                }
            )
            continue

        row = _save_result_to_watchlist(result, user_notes)
        report = None
        if include_reports:
            try:
                from services.research_report import build_research_report

                report = build_research_report(result.symbol, result.bucket)
            except Exception as exc:
                logger.warning("Report generation failed for %s: %s", result.symbol, exc)
        outcomes.append(
            {
                "symbol": result.symbol,
                "bucket": result.bucket.value,
                "price": result.price,
                "score": result.score,
                "summary": result.summary,
                "notes": row["notes"],
                "added": True,
                "error": None,
                "report": report,
            }
        )

    return outcomes


def refresh_watchlist(
    *,
    max_items: int | None = None,
    time_budget_seconds: float | None = None,
    per_symbol_timeout_seconds: float | None = 8.0,
) -> list[dict]:
    """Re-scan all watchlist symbols with fresh data."""
    items = cache_module.get_watchlist()
    if max_items and max_items > 0:
        items = items[:max_items]
    outcomes: list[dict] = []
    started = time.monotonic()

    for item in items:
        if time_budget_seconds and (time.monotonic() - started) >= time_budget_seconds:
            outcomes.append(
                {
                    "symbol": "__meta__",
                    "added": False,
                    "error": "time_budget_exceeded",
                    "partial": True,
                }
            )
            break
        symbol = item["symbol"]
        bucket = item.get("bucket", "medium")
        try:
            bucket_enum = Bucket(bucket)
        except ValueError:
            bucket_enum = Bucket.medium

        result, error = _analyze_with_timeout(symbol, bucket_enum, per_symbol_timeout_seconds)
        if error or result is None:
            outcomes.append(
                {
                    "symbol": symbol,
                    "added": False,
                    "error": error,
                    "price": item.get("price"),
                    "score": item.get("score"),
                }
            )
            continue

        row = _save_result_to_watchlist(result, "")
        outcomes.append(
            {
                "symbol": symbol,
                "added": True,
                "error": None,
                "price": row.get("price"),
                "score": row.get("score"),
                "last_scanned_at": row.get("last_scanned_at"),
            }
        )

    return outcomes
