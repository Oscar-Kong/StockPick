"""Analysis API — watchlist matrix, symbol deep-dive, compare."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from fastapi import APIRouter, HTTPException, Query

from config import ANALYZE_ROUTE_TIMEOUT_SECONDS, COMPARE_ROUTE_TIMEOUT_SECONDS, REPORT_ROUTE_TIMEOUT_SECONDS
from models.schemas import (
    AnalyzeCompareResponse,
    AnalyzeSymbolResponse,
    AnalyzeTimeSeriesDiagnosticsResponse,
    AnalyzeWatchlistResponse,
    Bucket,
)
from services.analyze_service import (
    build_compare,
    build_symbol_analysis,
    build_watchlist_matrix,
    get_cached_symbol_analysis,
    score_all_buckets,
)
from data import cache as cache_module
from utils.demo_guard import enforce_compare_symbols

router = APIRouter(prefix="/analyze", tags=["analyze"])
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="analyze-routes")


def _run_with_timeout(fn, *args, timeout_seconds: float, **kwargs):
    future = _EXECUTOR.submit(fn, *args, **kwargs)
    return future.result(timeout=max(1.0, timeout_seconds))


@router.get("/watchlist", response_model=AnalyzeWatchlistResponse)
def analyze_watchlist():
    rows = build_watchlist_matrix()
    alert_total = sum(r.get("alert_count", 0) for r in rows)
    return AnalyzeWatchlistResponse(rows=rows, alert_total=alert_total)


@router.get("/compare", response_model=AnalyzeCompareResponse)
def analyze_compare(symbols: str = Query(..., description="Comma-separated tickers, max 4")):
    parts = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not parts:
        raise HTTPException(status_code=400, detail="Provide at least one symbol")
    parts = enforce_compare_symbols(parts)
    if len(parts) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 symbols")
    try:
        data = _run_with_timeout(build_compare, parts, timeout_seconds=COMPARE_ROUTE_TIMEOUT_SECONDS)
        return AnalyzeCompareResponse(**data)
    except FuturesTimeout as exc:
        raise HTTPException(status_code=504, detail="Compare timed out — try fewer symbols") from exc


@router.get("/{symbol}/bucket-fit")
def analyze_symbol_bucket_fit(symbol: str):
    sym = symbol.upper()
    if sym == "COMPARE":
        raise HTTPException(status_code=404, detail="Invalid symbol")
    try:
        return _run_with_timeout(score_all_buckets, sym, timeout_seconds=ANALYZE_ROUTE_TIMEOUT_SECONDS)
    except FuturesTimeout as exc:
        raise HTTPException(status_code=504, detail="Bucket fit timed out") from exc


@router.get("/{symbol}/diagnostics", response_model=AnalyzeTimeSeriesDiagnosticsResponse)
def analyze_symbol_diagnostics(
    symbol: str,
    lookback: int = Query(252, ge=5, le=1260, description="Trading days of history"),
):
    sym = symbol.upper()
    if sym == "COMPARE":
        raise HTTPException(status_code=404, detail="Invalid symbol")
    from services.time_series_diagnostics_service import build_time_series_diagnostics

    try:
        data = _run_with_timeout(
            build_time_series_diagnostics,
            sym,
            lookback,
            timeout_seconds=ANALYZE_ROUTE_TIMEOUT_SECONDS,
        )
    except FuturesTimeout as exc:
        raise HTTPException(status_code=504, detail="Diagnostics timed out") from exc
    if data.get("price_bars", 0) == 0 and data.get("data_source") == "none":
        raise HTTPException(status_code=404, detail=f"No price history for {sym}")
    return AnalyzeTimeSeriesDiagnosticsResponse(**data)


@router.get("/{symbol}/report")
def analyze_symbol_report(symbol: str, bucket: Bucket | None = None):
    from services.research_report import build_research_report, get_cached_report

    sym = symbol.upper()
    if sym == "COMPARE":
        raise HTTPException(status_code=404, detail="Invalid symbol")

    sleeve = bucket.value if bucket else None
    cached = get_cached_report(sym, sleeve)
    if cached and not bucket:
        return cached
    try:
        data = _run_with_timeout(
            build_research_report,
            sym,
            bucket,
            timeout_seconds=REPORT_ROUTE_TIMEOUT_SECONDS,
        )
    except FuturesTimeout as exc:
        if cached:
            return cached
        raise HTTPException(status_code=504, detail="Report generation timed out") from exc
    if data.get("error"):
        if cached:
            return cached
        raise HTTPException(status_code=404, detail=data["error"])
    cache_module.save_report_snapshot(
        symbol=sym,
        bucket=bucket.value if bucket else None,
        report=data,
        title=f"{sym} report",
        notes="Auto-saved from /analyze/{symbol}/report",
    )
    return data


@router.get("/{symbol}", response_model=AnalyzeSymbolResponse)
def analyze_symbol_route(
    symbol: str,
    bucket: Bucket | None = None,
    refresh: bool = Query(False, description="Bypass in-memory cache"),
    include_bucket_fit: bool = Query(False, description="Score all three buckets (slower)"),
):
    if symbol.upper() == "COMPARE":
        raise HTTPException(status_code=404, detail="Use /analyze/compare")
    selected_bucket = bucket or Bucket.penny
    if not refresh:
        cached = get_cached_symbol_analysis(symbol, selected_bucket)
        if cached and not cached.get("error"):
            cached_scores = (cached.get("bucket_fit") or {}).get("scores") or {}
            if not include_bucket_fit or cached_scores:
                return AnalyzeSymbolResponse(**cached)
    try:
        data = _run_with_timeout(
            build_symbol_analysis,
            symbol,
            selected_bucket,
            timeout_seconds=ANALYZE_ROUTE_TIMEOUT_SECONDS,
            include_bucket_fit=include_bucket_fit,
            force_refresh=refresh,
        )
    except FuturesTimeout as exc:
        cached = get_cached_symbol_analysis(symbol, selected_bucket)
        if cached:
            data = cached
        else:
            raise HTTPException(status_code=504, detail="Analyze request timed out") from exc
    if data.get("error"):
        raise HTTPException(status_code=404, detail=data["error"])
    cache_module.save_analyze_snapshot(
        symbol=str(data.get("symbol") or symbol).upper(),
        bucket=selected_bucket.value,
        payload=data,
    )
    return AnalyzeSymbolResponse(**data)
