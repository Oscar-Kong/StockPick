"""Research job retry with duplicate guard."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from data.db_engine import get_engine
from engines.jobs.queue import dispatch_job, enqueue_job
from engines.quant_models import JobQueueItem
from models.schemas_research import JobRetryResponse
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def retry_research_job(job_id: str, *, window_minutes: int = 10) -> JobRetryResponse:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(JobQueueItem, job_id)
        if not row:
            return JobRetryResponse(job_id=job_id, duplicate_blocked=True, message="job_not_found")

        payload = json.loads(row.payload_json or "{}")
        cutoff = _utcnow() - timedelta(minutes=window_minutes)
        dup = (
            session.query(JobQueueItem)
            .filter(
                JobQueueItem.job_name == row.job_name,
                JobQueueItem.status.in_(("pending", "running")),
                JobQueueItem.created_at >= cutoff,
            )
            .first()
        )
        if dup:
            return JobRetryResponse(
                job_id=job_id,
                duplicate_blocked=True,
                message=f"duplicate_blocked:{dup.job_id}",
            )

        retry_payload = {**payload, "retry_of": job_id}
        try:
            result = dispatch_job(row.job_name, retry_payload)
            new_id = result.get("job_id") if isinstance(result, dict) else enqueue_job(row.job_name, retry_payload)
        except ValueError as exc:
            return JobRetryResponse(job_id=job_id, duplicate_blocked=True, message=str(exc))

        return JobRetryResponse(
            job_id=job_id,
            retried_as=str(new_id),
            duplicate_blocked=False,
            message="retry_enqueued",
        )
