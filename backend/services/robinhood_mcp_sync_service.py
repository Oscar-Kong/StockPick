"""Background Robinhood MCP sync jobs (non-blocking HTTP)."""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def start_robinhood_mcp_sync(*, run_decision: bool = False) -> str:
    from services.portfolio_snapshot_service import import_robinhood_mcp_and_decide

    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "started_at": _utcnow().isoformat() + "Z",
            "finished_at": None,
            "error": None,
            "result": None,
        }

    def _run() -> None:
        try:
            result = import_robinhood_mcp_and_decide(run_decision=run_decision)
            with _lock:
                job = _jobs.get(job_id)
                if job:
                    job["status"] = "completed"
                    job["finished_at"] = _utcnow().isoformat() + "Z"
                    job["result"] = result
        except Exception as exc:
            logger.exception("Robinhood MCP background sync failed")
            with _lock:
                job = _jobs.get(job_id)
                if job:
                    job["status"] = "failed"
                    job["finished_at"] = _utcnow().isoformat() + "Z"
                    job["error"] = str(exc)[:500]

    thread = threading.Thread(target=_run, name=f"rh-mcp-sync-{job_id[:8]}", daemon=True)
    thread.start()
    return job_id


def get_robinhood_mcp_sync_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None
