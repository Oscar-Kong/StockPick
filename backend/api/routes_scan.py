"""Scan API routes."""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from core.sleeve import normalize_sleeve
from data import cache as cache_module
from models.schemas import (
    Bucket,
    LatestScanResponse,
    ScanJobResponse,
    ScanOptions,
    ScanPickSummaryRequest,
    ScanPickSummaryResponse,
    ScanStatusResponse,
    StockResult,
)
from services.scan_manager import scan_manager
from services.scan_pick_summary import generate_scan_pick_summary
from utils.datetime_util import parse_api_datetime
from utils.demo_guard import enforce_scan_options
from utils.pydantic_util import json_safe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("/penny", response_model=ScanJobResponse)
def scan_penny(options: ScanOptions | None = None):
    options = enforce_scan_options(options)
    job = scan_manager.start_scan_async(Bucket.penny, options)
    return ScanJobResponse(job_id=job.job_id, bucket=Bucket.penny, status=job.status)


@router.post("/compounder", response_model=ScanJobResponse)
def scan_compounder(options: ScanOptions | None = None):
    options = enforce_scan_options(options)
    job = scan_manager.start_scan_async(Bucket.compounder, options)
    return ScanJobResponse(job_id=job.job_id, bucket=Bucket.compounder, status=job.status)


def _stock_result_from_row(row: dict | StockResult) -> StockResult | None:
    """Validate one cached/job row; skip schema-drift rows instead of 500ing the endpoint."""
    try:
        if isinstance(row, StockResult):
            payload = json_safe(row.model_dump())
        elif isinstance(row, dict):
            payload = json_safe(row)
        else:
            return None
        if not isinstance(payload, dict):
            return None
        if "bucket" in payload:
            payload["bucket"] = normalize_sleeve(str(payload.get("bucket") or "penny"))
        return StockResult(**payload)
    except (ValidationError, TypeError, ValueError) as exc:
        logger.warning("Skipping invalid StockResult row: %s", exc)
        return None


def _stock_results_from_rows(rows: list) -> tuple[list[StockResult], int]:
    out: list[StockResult] = []
    invalid = 0
    for r in rows or []:
        if isinstance(r, StockResult):
            parsed = _stock_result_from_row(r)
        elif isinstance(r, dict):
            parsed = _stock_result_from_row(r)
        else:
            invalid += 1
            continue
        if parsed is None:
            invalid += 1
        else:
            out.append(parsed)
    return out, invalid


@router.get("/latest/{bucket}", response_model=LatestScanResponse)
def get_latest_scan(bucket: Bucket):
    data = scan_manager.get_latest_scan(bucket)
    last_attempt = cache_module.get_last_scan_attempt_failure(bucket.value) or {}
    last_attempt_failed_at = parse_api_datetime(
        last_attempt.get("failed_at") if isinstance(last_attempt.get("failed_at"), str) else None
    )
    last_attempt_error = last_attempt.get("error")
    if not data:
        return LatestScanResponse(
            bucket=bucket,
            results=[],
            completed_at=None,
            last_attempt_failed_at=last_attempt_failed_at,
            last_attempt_error=last_attempt_error,
        )
    results, invalid_count = _stock_results_from_rows(data.get("results", []))
    completed = data.get("completed_at")
    cache_age = cache_module.get_latest_scan_cache_age_seconds(bucket.value)
    return LatestScanResponse(
        bucket=bucket,
        results=results,
        completed_at=parse_api_datetime(completed if isinstance(completed, str) else None),
        strategy_version=data.get("strategy_version"),
        parity_summary=data.get("parity_summary"),
        scoring_engine_used=data.get("scoring_engine_used"),
        timings=data.get("timings"),
        cache_age_seconds=cache_age,
        last_attempt_failed_at=last_attempt_failed_at,
        last_attempt_error=last_attempt_error,
        invalid_result_count=invalid_count,
    )


@router.post("/{bucket}/{symbol}/pick-summary", response_model=ScanPickSummaryResponse)
def scan_pick_summary(bucket: Bucket, symbol: str, body: ScanPickSummaryRequest):
    """Short AI note: company background + why this scan ranked the symbol."""
    result = generate_scan_pick_summary(
        symbol=symbol.upper(),
        bucket=bucket.value,
        score=body.score,
        summary=body.summary,
        signals=[s.model_dump() for s in body.signals],
        metrics=body.metrics,
        locale=body.locale or "en",
    )
    return ScanPickSummaryResponse(bucket=bucket, **result)


@router.get("/{job_id}", response_model=ScanStatusResponse)
def get_scan_status(job_id: str):
    job = scan_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    results, invalid_count = _stock_results_from_rows(job.results)

    return ScanStatusResponse(
        job_id=job.job_id,
        bucket=job.bucket,
        status=job.status,
        progress=job.progress,
        message=job.message if job.status != "failed" else (job.error or job.message),
        results=results,
        completed_at=job.completed_at,
        parity_summary=json_safe(job.parity_summary) if job.parity_summary else None,
        scoring_engine_used=job.scoring_engine_used,
        timings=json_safe(dict(job.timings)) if job.timings else None,
        invalid_result_count=invalid_count,
    )
