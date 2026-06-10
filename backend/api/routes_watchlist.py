"""Watchlist API routes."""
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime

from fastapi import APIRouter, HTTPException

from config import (
    WATCHLIST_IMPORT_GENERATE_REPORTS,
    WATCHLIST_IMPORT_PER_SYMBOL_TIMEOUT_SECONDS,
    WATCHLIST_REFRESH_BUDGET_SECONDS,
    WATCHLIST_REFRESH_MAX_ITEMS,
    WATCHLIST_REFRESH_PER_SYMBOL_TIMEOUT_SECONDS,
    WATCHLIST_REPORT_BUDGET_SECONDS,
    WATCHLIST_REPORT_MAX_ITEMS,
)
from data import cache as cache_module
from models.schemas import (
    Bucket,
    WatchlistCreate,
    WatchlistImportRequest,
    WatchlistImportResponse,
    WatchlistImportRow,
    WatchlistItem,
    WatchlistNotesUpdate,
    WatchlistRefreshResponse,
)
from services.symbol_parser import parse_symbols
from services.watchlist_scanner import import_to_watchlist, refresh_watchlist

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
_REPORT_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="watchlist-reports")


def _to_item(row: dict) -> WatchlistItem:
    last = row.get("last_scanned_at")
    return WatchlistItem(
        symbol=row["symbol"],
        bucket=Bucket(row["bucket"]),
        notes=row.get("notes", ""),
        added_at=datetime.fromisoformat(row["added_at"]),
        price=row.get("price"),
        score=row.get("score"),
        summary=row.get("summary") or "",
        last_scanned_at=datetime.fromisoformat(last) if last else None,
        earnings_date=row.get("earnings_date"),
        days_until_earnings=row.get("days_until_earnings"),
        valuation_warnings=row.get("valuation_warnings") or [],
    )


@router.get("", response_model=list[WatchlistItem])
def list_watchlist():
    return [_to_item(i) for i in cache_module.get_watchlist()]


@router.post("", response_model=WatchlistItem)
def add_watchlist_item(body: WatchlistCreate):
    result = cache_module.add_to_watchlist(body.symbol, body.bucket.value, body.notes)
    return _to_item(result)


@router.post("/import", response_model=WatchlistImportResponse)
def import_watchlist(body: WatchlistImportRequest):
    if not body.input.strip():
        raise HTTPException(status_code=400, detail="No tickers provided")

    if not parse_symbols(body.input):
        raise HTTPException(
            status_code=400,
            detail="Could not parse any valid tickers. Use symbols like AAPL, MSFT, BRK-B",
        )

    bucket_choice = body.bucket
    if isinstance(bucket_choice, str) and bucket_choice != "auto":
        try:
            bucket_choice = Bucket(bucket_choice)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid bucket") from exc

    outcomes = import_to_watchlist(
        body.input,
        bucket_choice,
        body.notes,
        include_reports=WATCHLIST_IMPORT_GENERATE_REPORTS,
        per_symbol_timeout_seconds=WATCHLIST_IMPORT_PER_SYMBOL_TIMEOUT_SECONDS,
    )
    rows = [WatchlistImportRow(**o) for o in outcomes]
    added = sum(1 for r in rows if r.added)
    return WatchlistImportResponse(
        results=rows,
        added_count=added,
        failed_count=len(rows) - added,
    )


@router.post("/refresh", response_model=WatchlistRefreshResponse)
def refresh_all_watchlist():
    outcomes = refresh_watchlist(
        max_items=WATCHLIST_REFRESH_MAX_ITEMS,
        time_budget_seconds=WATCHLIST_REFRESH_BUDGET_SECONDS,
        per_symbol_timeout_seconds=WATCHLIST_REFRESH_PER_SYMBOL_TIMEOUT_SECONDS,
    )
    refreshed = sum(1 for o in outcomes if o.get("added"))
    failed = len(outcomes) - refreshed
    return WatchlistRefreshResponse(refreshed=refreshed, failed=failed, results=outcomes)


@router.patch("/{symbol}/notes", response_model=WatchlistItem)
def update_watchlist_notes_route(symbol: str, body: WatchlistNotesUpdate):
    row = cache_module.update_watchlist_notes(symbol, body.notes)
    if not row:
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")
    return _to_item(row)


@router.post("/reports")
def generate_watchlist_reports():
    """Generate research reports for all watchlist symbols (may take several minutes)."""
    from models.schemas import Bucket
    from services.research_report import build_research_report

    items = cache_module.get_watchlist()[:WATCHLIST_REPORT_MAX_ITEMS]
    results: list[dict] = []
    started = time.monotonic()
    for item in items:
        if (time.monotonic() - started) >= WATCHLIST_REPORT_BUDGET_SECONDS:
            results.append({"symbol": "__meta__", "ok": False, "error": "time_budget_exceeded", "partial": True})
            break
        sym = item["symbol"]
        try:
            b = Bucket(item.get("bucket", "penny"))
            future = _REPORT_EXECUTOR.submit(build_research_report, sym, b)
            report = future.result(timeout=min(8.0, WATCHLIST_REPORT_BUDGET_SECONDS))
            results.append({"symbol": sym, "ok": not report.get("error"), "report": report})
        except FuturesTimeout:
            results.append({"symbol": sym, "ok": False, "error": "report_timeout"})
        except Exception as exc:
            results.append({"symbol": sym, "ok": False, "error": str(exc)})
    return {"generated": sum(1 for r in results if r.get("ok")), "results": results}


@router.delete("/{symbol}")
def remove_watchlist_item(symbol: str):
    removed = cache_module.remove_from_watchlist(symbol)
    if not removed:
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")
    return {"ok": True}
