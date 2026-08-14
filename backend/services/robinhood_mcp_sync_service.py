"""Background Robinhood MCP sync jobs (non-blocking HTTP)."""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
# One active sync per account key (ROBINHOOD_MCP_ACCOUNT_ID or "default").
_active_by_account: dict[str, str] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _account_key() -> str:
    return os.getenv("ROBINHOOD_MCP_ACCOUNT_ID", "").strip() or "default"


def _sync_deadline_sec() -> float:
    raw = os.getenv("ROBINHOOD_MCP_SYNC_TIMEOUT_SEC", "90").strip()
    try:
        return max(15.0, float(raw))
    except ValueError:
        return 90.0


def _mark_stale_active_jobs() -> None:
    """Flag overdue workers without releasing their single-flight ownership.

    Python threads cannot be cancelled safely. Releasing the account slot while
    the old worker is still importing lets two workers mutate the same portfolio.
    Keep the job running until the worker exits; the MCP client has its own hard
    network deadline and will eventually complete or fail normally.
    """
    now = time.monotonic()
    for job in _jobs.values():
        if job.get("status") != "running":
            continue
        deadline = job.get("deadline_monotonic")
        if deadline is not None and now > float(deadline) and not job.get("timed_out"):
            job["timed_out"] = True
            job["error"] = "Robinhood MCP sync exceeded soft deadline; worker is still stopping"
            job["phase"] = "timed_out_running"
            job["heartbeat"] = _utcnow().isoformat() + "Z"


def start_robinhood_mcp_sync(*, run_decision: bool = False) -> str:
    from services.portfolio_snapshot_service import import_robinhood_mcp_and_decide

    account_key = _account_key()
    with _lock:
        _mark_stale_active_jobs()
        existing_id = _active_by_account.get(account_key)
        if existing_id:
            existing = _jobs.get(existing_id)
            if existing and existing.get("status") == "running":
                existing["reused"] = True
                existing["heartbeat"] = _utcnow().isoformat() + "Z"
                return existing_id

        job_id = str(uuid.uuid4())
        deadline_sec = _sync_deadline_sec()
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "phase": "fetching",
            "started_at": _utcnow().isoformat() + "Z",
            "finished_at": None,
            "error": None,
            "result": None,
            "account_key": account_key,
            "deadline_sec": deadline_sec,
            "deadline_monotonic": time.monotonic() + deadline_sec,
            "heartbeat": _utcnow().isoformat() + "Z",
            "reused": False,
            "retry_count": 0,
            "timed_out": False,
        }
        _active_by_account[account_key] = job_id

    def _run() -> None:
        try:
            with _lock:
                job = _jobs.get(job_id)
                if job:
                    job["phase"] = "importing"
                    job["heartbeat"] = _utcnow().isoformat() + "Z"
            result = import_robinhood_mcp_and_decide(run_decision=run_decision)
            with _lock:
                job = _jobs.get(job_id)
                if job:
                    # Soft-timeout may have already marked this job failed.
                    if job.get("status") == "running":
                        job["status"] = "completed"
                        job["phase"] = "committed"
                        job["finished_at"] = _utcnow().isoformat() + "Z"
                        job["result"] = result
                        job["heartbeat"] = _utcnow().isoformat() + "Z"
                    if _active_by_account.get(account_key) == job_id:
                        _active_by_account.pop(account_key, None)
        except Exception as exc:
            logger.exception("Robinhood MCP background sync failed")
            with _lock:
                job = _jobs.get(job_id)
                if job:
                    if job.get("status") == "running":
                        job["status"] = "failed"
                        job["phase"] = "failed"
                        job["finished_at"] = _utcnow().isoformat() + "Z"
                        job["error"] = str(exc)[:500]
                        job["heartbeat"] = _utcnow().isoformat() + "Z"
                    if _active_by_account.get(account_key) == job_id:
                        _active_by_account.pop(account_key, None)

    thread = threading.Thread(target=_run, name=f"rh-mcp-sync-{job_id[:8]}", daemon=True)
    thread.start()
    return job_id


def get_robinhood_mcp_sync_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        _mark_stale_active_jobs()
        job = _jobs.get(job_id)
        if not job:
            return None
        out = dict(job)
        # Internal monotonic deadline is not API-facing.
        out.pop("deadline_monotonic", None)
        return out
