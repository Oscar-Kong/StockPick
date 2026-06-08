"""Saved scans and saved reports CRUD routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from data import cache as cache_module
from models.schemas import (
    Bucket,
    SavedAnalyzeItem,
    SavedProgressSummary,
    SavedReportCreateRequest,
    SavedReportItem,
    SavedReportUpdateRequest,
    SavedScanCreateRequest,
    SavedScanItem,
    StockResult,
)

router = APIRouter(prefix="/saved", tags=["saved"])


def _to_saved_scan_item(row: dict) -> SavedScanItem:
    completed = row.get("completed_at")
    return SavedScanItem(
        id=int(row["id"]),
        name=row.get("name") or "",
        bucket=Bucket(row["bucket"]),
        options=row.get("options") or {},
        results=[StockResult(**r) for r in (row.get("results") or [])],
        result_count=int(row.get("result_count") or 0),
        strategy_version=row.get("strategy_version"),
        completed_at=datetime.fromisoformat(completed) if completed else None,
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _to_saved_report_item(row: dict) -> SavedReportItem:
    bucket = row.get("bucket")
    return SavedReportItem(
        id=int(row["id"]),
        symbol=row["symbol"],
        bucket=Bucket(bucket) if bucket else None,
        title=row.get("title") or "",
        notes=row.get("notes") or "",
        report=row.get("report") or {},
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _to_saved_analyze_item(row: dict) -> SavedAnalyzeItem:
    return SavedAnalyzeItem(
        id=int(row["id"]),
        symbol=row["symbol"],
        bucket=Bucket(row["bucket"]),
        payload=row.get("payload") or {},
        score=row.get("score"),
        data_quality_score=row.get("data_quality_score"),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


@router.get("/scans", response_model=list[SavedScanItem])
def list_saved_scans(bucket: Bucket | None = None, limit: int = Query(default=50, ge=1, le=200)):
    rows = cache_module.list_saved_scans(bucket.value if bucket else None, limit=limit)
    return [_to_saved_scan_item(r) for r in rows]


@router.post("/scans", response_model=SavedScanItem)
def create_saved_scan(body: SavedScanCreateRequest):
    row = cache_module.save_scan_snapshot(
        name=body.name,
        bucket=body.bucket.value,
        options=body.options,
        results=[r.model_dump(mode="json") for r in body.results],
        strategy_version=body.strategy_version,
        completed_at=body.completed_at,
    )
    return _to_saved_scan_item(row)


@router.get("/scans/{scan_id}", response_model=SavedScanItem)
def get_saved_scan(scan_id: int):
    row = cache_module.get_saved_scan(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Saved scan not found")
    return _to_saved_scan_item(row)


@router.delete("/scans/{scan_id}")
def delete_saved_scan(scan_id: int):
    ok = cache_module.delete_saved_scan(scan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Saved scan not found")
    return {"ok": True}


@router.get("/reports", response_model=list[SavedReportItem])
def list_saved_reports(symbol: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
    rows = cache_module.list_saved_reports(symbol=symbol.upper() if symbol else None, limit=limit)
    return [_to_saved_report_item(r) for r in rows]


@router.post("/reports", response_model=SavedReportItem)
def create_saved_report(body: SavedReportCreateRequest):
    row = cache_module.save_report_snapshot(
        symbol=body.symbol,
        bucket=body.bucket.value if body.bucket else None,
        title=body.title,
        notes=body.notes,
        report=body.report,
    )
    return _to_saved_report_item(row)


@router.get("/reports/{report_id}", response_model=SavedReportItem)
def get_saved_report(report_id: int):
    row = cache_module.get_saved_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Saved report not found")
    return _to_saved_report_item(row)


@router.patch("/reports/{report_id}", response_model=SavedReportItem)
def patch_saved_report(report_id: int, body: SavedReportUpdateRequest):
    row = cache_module.update_saved_report(
        report_id,
        title=body.title,
        notes=body.notes,
        report=body.report,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Saved report not found")
    return _to_saved_report_item(row)


@router.delete("/reports/{report_id}")
def delete_saved_report(report_id: int):
    ok = cache_module.delete_saved_report(report_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Saved report not found")
    return {"ok": True}


@router.get("/analyze", response_model=list[SavedAnalyzeItem])
def list_saved_analyze(
    symbol: str | None = None,
    bucket: Bucket | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = cache_module.list_saved_analyze(
        symbol=symbol.upper() if symbol else None,
        bucket=bucket.value if bucket else None,
        limit=limit,
    )
    return [_to_saved_analyze_item(r) for r in rows]


@router.get("/analyze/latest/{symbol}", response_model=SavedAnalyzeItem)
def get_latest_saved_analyze(symbol: str, bucket: Bucket | None = None):
    row = cache_module.get_latest_saved_analyze(symbol=symbol, bucket=bucket.value if bucket else None)
    if not row:
        raise HTTPException(status_code=404, detail="Saved analyze not found")
    return _to_saved_analyze_item(row)


@router.get("/progress-summary", response_model=SavedProgressSummary)
def progress_summary():
    latest_scan_rows = cache_module.list_saved_scans(limit=1)
    latest_report_rows = cache_module.list_saved_reports(limit=1)
    latest_analyze_rows = cache_module.list_saved_analyze(limit=1)
    latest_trade_rows = cache_module.list_trades(limit=1)
    scan_count = cache_module.count_saved_scans()
    report_count = cache_module.count_saved_reports()
    analyze_count = cache_module.count_saved_analyze()
    trade_count = cache_module.count_trades()

    latest_scan = latest_scan_rows[0] if latest_scan_rows else None
    latest_report = latest_report_rows[0] if latest_report_rows else None
    latest_analyze = latest_analyze_rows[0] if latest_analyze_rows else None
    latest_trade = latest_trade_rows[0] if latest_trade_rows else None

    return SavedProgressSummary(
        scan_count=scan_count,
        report_count=report_count,
        analyze_count=analyze_count,
        trade_count=trade_count,
        latest_scan_bucket=Bucket(latest_scan["bucket"]) if latest_scan else None,
        latest_scan_at=datetime.fromisoformat(latest_scan["created_at"]) if latest_scan else None,
        latest_report_symbol=latest_report["symbol"] if latest_report else None,
        latest_report_at=datetime.fromisoformat(latest_report["updated_at"]) if latest_report else None,
        latest_analyze_symbol=latest_analyze["symbol"] if latest_analyze else None,
        latest_analyze_bucket=Bucket(latest_analyze["bucket"]) if latest_analyze else None,
        latest_analyze_at=datetime.fromisoformat(latest_analyze["updated_at"])
        if latest_analyze
        else None,
        latest_trade_symbol=latest_trade["symbol"] if latest_trade else None,
        latest_trade_at=datetime.fromisoformat(latest_trade["updated_at"]) if latest_trade else None,
    )

