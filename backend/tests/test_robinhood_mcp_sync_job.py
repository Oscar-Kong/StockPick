"""Tests for background Robinhood MCP sync jobs."""
from __future__ import annotations

from unittest.mock import patch

from services.robinhood_mcp_sync_service import get_robinhood_mcp_sync_job, start_robinhood_mcp_sync


def test_mcp_sync_job_completes():
    with patch(
        "services.portfolio_snapshot_service.import_robinhood_mcp_and_decide",
        return_value={"holdings_count": 3, "orders_imported": 5},
    ):
        job_id = start_robinhood_mcp_sync(run_decision=False)
    import threading
    import time

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
