"""Tests for background Robinhood MCP sync jobs."""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

from services import robinhood_mcp_sync_service as sync_svc
from services.robinhood_mcp_sync_service import get_robinhood_mcp_sync_job, start_robinhood_mcp_sync


def _reset_jobs():
    with sync_svc._lock:
        sync_svc._jobs.clear()
        sync_svc._active_by_account.clear()


def test_mcp_sync_job_completes():
    _reset_jobs()
    with patch(
        "services.portfolio_snapshot_service.import_robinhood_mcp_and_decide",
        return_value={"holdings_count": 3, "orders_imported": 5},
    ):
        job_id = start_robinhood_mcp_sync(run_decision=False)

    deadline = time.time() + 5
    job = None
    while time.time() < deadline:
        job = get_robinhood_mcp_sync_job(job_id)
        if job and job["status"] != "running":
            break
        time.sleep(0.05)
    assert job is not None
    assert job["status"] == "completed"
    assert job["result"]["holdings_count"] == 3
    assert job["phase"] == "committed"


def test_concurrent_sync_returns_same_job_id():
    _reset_jobs()
    started = threading.Event()
    release = threading.Event()

    def slow_import(**_kwargs):
        started.set()
        release.wait(timeout=5)
        return {"holdings_count": 1}

    with patch(
        "services.portfolio_snapshot_service.import_robinhood_mcp_and_decide",
        side_effect=slow_import,
    ):
        first = start_robinhood_mcp_sync(run_decision=False)
        assert started.wait(timeout=2)
        second = start_robinhood_mcp_sync(run_decision=False)
        assert first == second
        job = get_robinhood_mcp_sync_job(first)
        assert job is not None
        assert job["reused"] is True
        release.set()

    deadline = time.time() + 5
    while time.time() < deadline:
        job = get_robinhood_mcp_sync_job(first)
        if job and job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "completed"
