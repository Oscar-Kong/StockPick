"""Job dispatch — sync (default), DB table, or Redis list."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from config import (
    FACTOR_MODEL_VERSION,
    JOB_QUEUE_BACKEND,
    JOB_QUEUE_REDIS_KEY,
    REDIS_URL,
    STRATEGY_VERSION,
)
from data.db_engine import get_engine
from engines.jobs.handlers import run_job
from engines.quant_models import JobQueueItem

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def effective_backend() -> str:
    backend = JOB_QUEUE_BACKEND.lower()
    if backend == "redis" and not REDIS_URL:
        logger.warning("JOB_QUEUE_BACKEND=redis but REDIS_URL unset; falling back to db")
        return "db"
    if backend not in ("sync", "db", "redis"):
        return "sync"
    return backend


def _redis_client():
    import redis

    return redis.from_url(REDIS_URL, decode_responses=True)


def redis_available() -> bool:
    if not REDIS_URL:
        return False
    try:
        client = _redis_client()
        client.ping()
        return True
    except Exception:
        return False


def enqueue_job(job_name: str, payload: dict[str, Any] | None = None) -> str:
    """Queue a job or run inline when backend=sync."""
    job_id = str(uuid.uuid4())
    payload = payload or {}
    backend = effective_backend()

    if backend == "sync":
        process_job(job_id, job_name, payload, backend="sync")
        return job_id

    if backend == "redis":
        client = _redis_client()
        client.rpush(
            JOB_QUEUE_REDIS_KEY,
            json.dumps(
                {
                    "job_id": job_id,
                    "job_name": job_name,
                    "payload": payload,
                    "strategy_version": STRATEGY_VERSION,
                    "factor_model_version": FACTOR_MODEL_VERSION,
                }
            ),
        )
        return job_id

    engine = get_engine()
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        session.add(
            JobQueueItem(
                job_id=job_id,
                job_name=job_name,
                payload_json=json.dumps(payload),
                status="pending",
                strategy_version=STRATEGY_VERSION,
                factor_model_version=FACTOR_MODEL_VERSION,
                created_at=_utcnow(),
            )
        )
        session.commit()
    return job_id


def dispatch_job(job_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Scheduler entry: enqueue or run synchronously."""
    backend = effective_backend()
    if backend == "sync":
        return run_job(job_name, payload)
    job_id = enqueue_job(job_name, payload)
    return {"queued": True, "job_id": job_id, "backend": backend}


def process_job(
    job_id: str,
    job_name: str,
    payload: dict[str, Any],
    *,
    backend: str = "db",
) -> dict[str, Any]:
    from engines.audit.logger import audit_log

    if backend == "db":
        _mark_db(job_id, status="running", started_at=_utcnow())

    audit_log(
        "job_started",
        payload={"job_id": job_id, "job_name": job_name, "backend": backend},
    )
    try:
        result = run_job(job_name, payload)
        if backend == "db":
            _mark_db(job_id, status="done", finished_at=_utcnow())
        audit_log(
            "job_finished",
            payload={"job_id": job_id, "job_name": job_name, "status": "done"},
        )
        return result
    except Exception as exc:
        if backend == "db":
            _mark_db(job_id, status="failed", finished_at=_utcnow(), error=str(exc)[:500])
        audit_log(
            "job_failed",
            payload={"job_id": job_id, "job_name": job_name, "error": str(exc)[:500]},
        )
        raise


def _mark_db(
    job_id: str,
    *,
    status: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error: str | None = None,
) -> None:
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        row = session.get(JobQueueItem, job_id)
        if not row:
            return
        row.status = status
        if started_at:
            row.started_at = started_at
        if finished_at:
            row.finished_at = finished_at
        if error:
            row.error_message = error
        session.commit()


def dequeue_one() -> dict[str, Any] | None:
    """Worker: take next job from Redis or DB queue."""
    backend = effective_backend()
    if backend == "redis":
        client = _redis_client()
        raw = client.blpop(JOB_QUEUE_REDIS_KEY, timeout=2)
        if not raw:
            return None
        return json.loads(raw[1])

    if backend != "db":
        return None

    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        row = (
            session.query(JobQueueItem)
            .filter(JobQueueItem.status == "pending")
            .order_by(JobQueueItem.created_at.asc())
            .first()
        )
        if not row:
            return None
        row.status = "running"
        row.started_at = _utcnow()
        session.commit()
        return {
            "job_id": row.job_id,
            "job_name": row.job_name,
            "payload": json.loads(row.payload_json or "{}"),
        }


def list_queued_jobs(limit: int = 20) -> list[dict[str, Any]]:
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        rows = (
            session.query(JobQueueItem)
            .order_by(JobQueueItem.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "job_id": r.job_id,
                "job_name": r.job_name,
                "status": r.status,
                "strategy_version": r.strategy_version,
                "factor_model_version": r.factor_model_version,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "error_message": r.error_message,
            }
            for r in rows
        ]
