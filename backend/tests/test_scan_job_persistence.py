from __future__ import annotations

from unittest.mock import patch

from models.schemas import Bucket, RiskLevel, ScanStatus, StockResult
from services.scan_service import ScanService


def test_completed_scan_job_can_be_read_after_process_memory_is_lost():
    persisted = {
        "job_id": "job-123",
        "bucket": "penny",
        "status": "completed",
        "progress": 100.0,
        "message": "Partial universe coverage 56%",
        "results": [
            {
                "symbol": "SAFE",
                "price": 2.5,
                "score": 80.0,
                "signals": [],
                "risk_level": "medium",
                "bucket": "penny",
                "metrics": {"final_rank": 1},
            }
        ],
        "completed_at": "2026-08-14T10:40:00",
        "scan_completeness": "partial",
        "published_as_latest": False,
        "diagnostics": {
            "coverage_diagnostics": {
                "provider_requested": 30,
                "provider_received": 12,
                "provider_deferred": 101,
            },
            "skipped_candidates": [{"symbol": "MISS", "reason": "missing_history"}],
        },
    }

    with patch("services.scan_service.cache_module.get_scan_job", return_value=persisted):
        job = ScanService().get_status("job-123")

    assert job is not None
    assert job.status == ScanStatus.completed
    assert job.bucket == Bucket.penny
    assert job.scan_completeness == "partial"
    assert job.published_as_latest is False
    assert job.diagnostics["coverage_diagnostics"]["provider_deferred"] == 101
    assert job.diagnostics["skipped_candidates"][0]["symbol"] == "MISS"
    assert isinstance(job.results[0], StockResult)
    assert job.results[0].risk_level == RiskLevel.medium
