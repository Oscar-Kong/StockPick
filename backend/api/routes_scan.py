"""Scan API routes."""
from datetime import datetime

from fastapi import APIRouter, HTTPException

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

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("/penny", response_model=ScanJobResponse)
def scan_penny(options: ScanOptions | None = None):
    job = scan_manager.start_scan_async(Bucket.penny, options)
    return ScanJobResponse(job_id=job.job_id, bucket=Bucket.penny, status=job.status)


@router.post("/medium", response_model=ScanJobResponse)
def scan_medium(options: ScanOptions | None = None):
    raise HTTPException(
        status_code=410,
        detail="Medium bucket is deprecated. Use POST /scan/penny or POST /scan/compounder.",
    )


@router.post("/compounder", response_model=ScanJobResponse)
def scan_compounder(options: ScanOptions | None = None):
    job = scan_manager.start_scan_async(Bucket.compounder, options)
    return ScanJobResponse(job_id=job.job_id, bucket=Bucket.compounder, status=job.status)


@router.get("/latest/{bucket}", response_model=LatestScanResponse)
def get_latest_scan(bucket: Bucket):
    data = scan_manager.get_latest_scan(bucket)
    last_attempt = cache_module.get_last_scan_attempt_failure(bucket.value) or {}
    last_attempt_failed_at = last_attempt.get("failed_at")
    last_attempt_error = last_attempt.get("error")
    if not data:
        return LatestScanResponse(
            bucket=bucket,
            results=[],
            completed_at=None,
            last_attempt_failed_at=(
                datetime.fromisoformat(last_attempt_failed_at.replace("Z", ""))
                if isinstance(last_attempt_failed_at, str)
                else None
            ),
            last_attempt_error=last_attempt_error,
        )
    results = [StockResult(**r) for r in data.get("results", [])]
    completed = data.get("completed_at")
    cache_age = cache_module.get_latest_scan_cache_age_seconds(bucket.value)
    return LatestScanResponse(
        bucket=bucket,
        results=results,
        completed_at=datetime.fromisoformat(completed) if completed else None,
        strategy_version=data.get("strategy_version"),
        parity_summary=data.get("parity_summary"),
        scoring_engine_used=data.get("scoring_engine_used"),
        timings=data.get("timings"),
        cache_age_seconds=cache_age,
        last_attempt_failed_at=(
            datetime.fromisoformat(last_attempt_failed_at.replace("Z", ""))
            if isinstance(last_attempt_failed_at, str)
            else None
        ),
        last_attempt_error=last_attempt_error,
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
    return ScanStatusResponse(
        job_id=job.job_id,
        bucket=job.bucket,
        status=job.status,
        progress=job.progress,
        message=job.message if job.status != "failed" else (job.error or job.message),
        results=job.results,
        completed_at=job.completed_at,
        parity_summary=job.parity_summary,
        scoring_engine_used=job.parity_summary.get("scoring_engine_used") if job.parity_summary else None,
        timings=dict(job.timings) if job.timings else None,
    )
