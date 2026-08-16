"""Deep Scan module — job lifecycle and public read surface for ranked evidence."""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from config import SCAN_STAGE_B_TOP_N
from data import cache as cache_module
from models.schemas import Bucket, ScanOptions, ScanStatus, StockResult
from core.sleeve import normalize_sleeve
from screeners.base import BaseScreener
from screeners.compounder import CompounderScreener
from screeners.penny import PennyScreener
from services.scan_display import refresh_results_return_metrics
from services.scan_pipeline import run_scan_pipeline

logger = logging.getLogger(__name__)

STAGE_B_TOP_N = SCAN_STAGE_B_TOP_N


@dataclass
class ScanJob:
    job_id: str
    bucket: Bucket
    status: ScanStatus = ScanStatus.pending
    progress: float = 0.0
    message: str = ""
    results: list[StockResult] = field(default_factory=list)
    completed_at: datetime | None = None
    error: str | None = None
    parity_summary: dict | None = None
    timings: dict[str, float] = field(default_factory=dict)
    scoring_engine_used: bool | None = None
    scoring_mode: str | None = None
    scan_completeness: str | None = None
    published_as_latest: bool | None = None


class ScanService:
    """Small interface over the Scan pipeline: start, read latest, read job status."""

    def __init__(self) -> None:
        self._jobs: dict[str, ScanJob] = {}
        self._lock = threading.Lock()

    def create_job(self, bucket: Bucket) -> ScanJob:
        job = ScanJob(job_id=str(uuid.uuid4()), bucket=bucket)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get_status(self, job_id: str) -> ScanJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is not None:
            return job
        payload = cache_module.get_scan_job(job_id)
        if not payload:
            return None
        try:
            completed_at = payload.get("completed_at")
            return ScanJob(
                job_id=str(payload["job_id"]),
                bucket=Bucket(str(payload["bucket"])),
                status=ScanStatus(str(payload.get("status") or ScanStatus.completed.value)),
                progress=float(payload.get("progress") or 0.0),
                message=str(payload.get("message") or ""),
                results=[StockResult(**row) for row in payload.get("results") or []],
                completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
                error=payload.get("error"),
                parity_summary=payload.get("parity_summary"),
                timings=dict(payload.get("timings") or {}),
                scoring_engine_used=payload.get("scoring_engine_used"),
                scoring_mode=payload.get("scoring_mode"),
                scan_completeness=payload.get("scan_completeness"),
                published_as_latest=payload.get("published_as_latest"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Ignoring invalid persisted scan job %s: %s", job_id, exc)
            return None

    get_job = get_status

    def persist_job(self, job: ScanJob) -> None:
        cache_module.save_scan_job(
            job.job_id,
            {
                "job_id": job.job_id,
                "bucket": job.bucket.value,
                "status": job.status.value,
                "progress": job.progress,
                "message": job.message,
                "results": [row.model_dump(mode="json") for row in job.results],
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error": job.error,
                "parity_summary": job.parity_summary,
                "timings": job.timings,
                "scoring_engine_used": job.scoring_engine_used,
                "scoring_mode": job.scoring_mode,
                "scan_completeness": job.scan_completeness,
                "published_as_latest": job.published_as_latest,
            },
        )

    def get_active_jobs_for_buckets(self, buckets: tuple[str, ...] | list[str]) -> list[ScanJob]:
        allowed = {b.lower() for b in buckets}
        with self._lock:
            return [
                job
                for job in self._jobs.values()
                if job.bucket.value in allowed
                and job.status in (ScanStatus.pending, ScanStatus.running)
            ]

    def get_latest(self, bucket: Bucket) -> dict | None:
        latest = cache_module.get_latest_scan(bucket.value)
        if latest:
            results = latest.get("results", [])
            if results and isinstance(results[0], dict):
                latest = {**latest, "results": refresh_results_return_metrics(results)}
            return latest
        saved = cache_module.list_saved_scans(bucket=bucket.value, limit=1)
        if saved:
            row = saved[0]
            results = row.get("results", [])
            if results and isinstance(results[0], dict):
                results = refresh_results_return_metrics(results)
            return {
                "results": results,
                "completed_at": row.get("completed_at") or row.get("created_at"),
                "strategy_version": row.get("strategy_version"),
            }
        return None

    get_latest_scan = get_latest

    def _get_screener(self, bucket: Bucket) -> BaseScreener:
        sleeve = normalize_sleeve(bucket.value)
        if sleeve == "compounder":
            return CompounderScreener()
        return PennyScreener()

    def run_scan(self, job_id: str, options: ScanOptions | None = None) -> None:
        run_scan_pipeline(self, job_id, options)

    def start_async(self, bucket: Bucket, options: ScanOptions | None = None) -> ScanJob:
        job = self.create_job(bucket)
        thread = threading.Thread(target=self.run_scan, args=(job.job_id, options), daemon=True)
        thread.start()
        return job

    start_scan_async = start_async


scan_service = ScanService()

# Backwards-compatible aliases
ScanManager = ScanService
scan_manager = scan_service
