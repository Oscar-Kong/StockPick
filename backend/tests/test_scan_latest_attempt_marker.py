"""GET /scan/latest must tolerate bad timestamps and invalid cached rows."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.routes_scan import get_latest_scan
from models.schemas import Bucket


def test_latest_scan_surfaces_failed_attempt_marker_with_prior_results():
    prior_completed = "2026-06-11T09:00:00"
    prior_payload = {
        "results": [],
        "completed_at": prior_completed,
        "strategy_version": "2026-05-eod-v1",
        "timings": {"stage_a_ms": 1234.5, "stage_b_ms": 9876.5, "total_ms": 11200.0},
    }
    attempt = {"failed_at": "2026-06-11T09:10:00Z", "error": "provider down"}

    with patch("api.routes_scan.scan_manager.get_latest_scan", return_value=prior_payload):
        with patch("api.routes_scan.cache_module.get_last_scan_attempt_failure", return_value=attempt):
            with patch(
                "api.routes_scan.cache_module.get_latest_scan_cache_age_seconds",
                return_value=42.5,
            ):
                resp = get_latest_scan(Bucket.penny)

    assert resp.completed_at.isoformat().startswith("2026-06-11T09:00:00")
    assert resp.last_attempt_failed_at is not None
    assert resp.last_attempt_failed_at.isoformat().startswith("2026-06-11T09:10:00")
    assert resp.last_attempt_error == "provider down"
    assert resp.cache_age_seconds == 42.5
    assert resp.timings == {"stage_a_ms": 1234.5, "stage_b_ms": 9876.5, "total_ms": 11200.0}


def test_latest_scan_with_no_prior_results_still_returns_failed_marker():
    attempt = {"failed_at": "2026-06-11T09:10:00Z", "error": "first attempt died"}
    with patch("api.routes_scan.scan_manager.get_latest_scan", return_value=None):
        with patch("api.routes_scan.cache_module.get_last_scan_attempt_failure", return_value=attempt):
            resp = get_latest_scan(Bucket.penny)
    assert resp.results == []
    assert resp.completed_at is None
    assert resp.last_attempt_failed_at is not None
    assert resp.last_attempt_error == "first attempt died"


def test_latest_scan_without_failed_attempt_marker_is_clean():
    payload = {"results": [], "completed_at": "2026-06-11T09:00:00", "strategy_version": "v1"}
    with patch("api.routes_scan.scan_manager.get_latest_scan", return_value=payload):
        with patch("api.routes_scan.cache_module.get_last_scan_attempt_failure", return_value=None):
            with patch("api.routes_scan.cache_module.get_latest_scan_cache_age_seconds", return_value=10.0):
                resp = get_latest_scan(Bucket.penny)
    assert resp.last_attempt_failed_at is None
    assert resp.last_attempt_error is None
    assert resp.cache_age_seconds == 10.0


def test_latest_scan_malformed_failed_at_returns_none():
    attempt = {"failed_at": "not-a-timestamp", "error": "boom"}
    with patch("api.routes_scan.scan_manager.get_latest_scan", return_value=None):
        with patch("api.routes_scan.cache_module.get_last_scan_attempt_failure", return_value=attempt):
            resp = get_latest_scan(Bucket.penny)
    assert resp.last_attempt_failed_at is None
    assert resp.last_attempt_error == "boom"


def test_latest_scan_skips_invalid_rows():
    payload = {
        "results": [
            {
                "symbol": "GOOD",
                "price": 10.0,
                "score": 80.0,
                "bucket": "penny",
                "risk_level": "medium",
            },
            {
                "symbol": "BAD",
                "price": None,
                "score": 999.0,
                "bucket": "medium",
                "risk_level": "nope",
            },
        ],
        "completed_at": "2026-06-11T09:00:00Z",
    }
    with patch("api.routes_scan.scan_manager.get_latest_scan", return_value=payload):
        with patch("api.routes_scan.cache_module.get_last_scan_attempt_failure", return_value=None):
            with patch("api.routes_scan.cache_module.get_latest_scan_cache_age_seconds", return_value=1.0):
                resp = get_latest_scan(Bucket.penny)
    assert len(resp.results) == 1
    assert resp.results[0].symbol == "GOOD"
    assert resp.invalid_result_count == 1
    assert resp.completed_at is not None
