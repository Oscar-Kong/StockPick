"""Saved progress-summary must not crash when records exist; legacy buckets normalize."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.routes_saved import _to_saved_scan_item, progress_summary
from models.schemas import Bucket


def test_progress_summary_with_populated_records():
    scan = {
        "id": 1,
        "bucket": "medium",
        "created_at": "2026-06-11T09:00:00Z",
        "name": "scan",
        "options": {},
        "results": [],
        "result_count": 0,
    }
    report = {
        "id": 2,
        "symbol": "AAA",
        "updated_at": "2026-06-11T09:05:00Z",
    }
    analyze = {
        "id": 3,
        "symbol": "BBB",
        "bucket": "medium",
        "updated_at": "2026-06-11T09:06:00Z",
    }
    trade = {
        "id": 4,
        "symbol": "CCC",
        "updated_at": "2026-06-11T09:07:00Z",
    }
    with (
        patch("api.routes_saved.cache_module.list_saved_scans", return_value=[scan]),
        patch("api.routes_saved.cache_module.list_saved_reports", return_value=[report]),
        patch("api.routes_saved.cache_module.list_saved_analyze", return_value=[analyze]),
        patch("api.routes_saved.cache_module.list_trades", return_value=[trade]),
        patch("api.routes_saved.cache_module.count_saved_scans", return_value=1),
        patch("api.routes_saved.cache_module.count_saved_reports", return_value=1),
        patch("api.routes_saved.cache_module.count_saved_analyze", return_value=1),
        patch("api.routes_saved.cache_module.count_trades", return_value=1),
    ):
        summary = progress_summary()

    assert summary.scan_count == 1
    assert summary.latest_scan_bucket == Bucket.penny
    assert summary.latest_scan_at is not None
    assert summary.latest_report_symbol == "AAA"
    assert summary.latest_report_at is not None
    assert summary.latest_analyze_bucket == Bucket.penny
    assert summary.latest_analyze_at is not None
    assert summary.latest_trade_symbol == "CCC"
    assert summary.latest_trade_at is not None


def test_saved_scan_normalizes_legacy_medium_bucket():
    row = {
        "id": 9,
        "name": "legacy",
        "bucket": "medium",
        "options": {},
        "results": [],
        "result_count": 0,
        "created_at": "2026-06-11T09:00:00Z",
        "completed_at": "2026-06-11T09:01:00Z",
    }
    item = _to_saved_scan_item(row)
    assert item.bucket == Bucket.penny
