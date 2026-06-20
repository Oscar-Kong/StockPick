"""Experiment job persistence — discrete stages, no fake progress percentages."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from data.db_engine import get_engine
from engines.quant_models import ResearchExperimentJob
from models.schemas_research import ExperimentJobResponse, ExperimentStageRecord
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session

STAGE_ORDER = [
    "validating",
    "resolving_universe",
    "loading_prices",
    "calculating_features",
    "running_analysis",
    "calculating_outcomes",
    "evaluating_reliability",
    "persisting_result",
    "complete",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_stages(raw: str) -> list[ExperimentStageRecord]:
    data = json_loads(raw, [])
    out: list[ExperimentStageRecord] = []
    if not isinstance(data, list):
        return out
    for item in data:
        if isinstance(item, dict) and item.get("stage"):
            out.append(ExperimentStageRecord(**item))
    return out


def _to_response(row: ResearchExperimentJob) -> ExperimentJobResponse:
    status = row.status
    if status == "done":
        status = "completed"
    return ExperimentJobResponse(
        job_id=row.job_id,
        experiment_id=row.experiment_id,
        status=status,  # type: ignore[arg-type]
        current_stage=row.current_stage,  # type: ignore[arg-type]
        stages=_parse_stages(row.stages_json or "[]"),
        run_id=row.run_id,
        last_success_run_id=row.last_success_run_id,
        error_message=row.error_message,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def create_job(experiment_id: str) -> ExperimentJobResponse:
    job_id = f"expjob_{uuid.uuid4().hex[:12]}"
    now = _utcnow()
    stages = [
        ExperimentStageRecord(stage=s, status="pending")  # type: ignore[arg-type]
        for s in STAGE_ORDER
    ]
    engine = get_engine()
    with Session(engine) as session:
        row = ResearchExperimentJob(
            job_id=job_id,
            experiment_id=experiment_id,
            status="pending",
            current_stage="validating",
            stages_json=json_dumps([s.model_dump(mode="json") for s in stages]),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_response(row)


def get_active_job(experiment_id: str) -> ResearchExperimentJob | None:
    engine = get_engine()
    with Session(engine) as session:
        return (
            session.query(ResearchExperimentJob)
            .filter(
                ResearchExperimentJob.experiment_id == experiment_id,
                ResearchExperimentJob.status.in_(("pending", "running")),
            )
            .order_by(ResearchExperimentJob.created_at.desc())
            .first()
        )


def get_job(job_id: str) -> ExperimentJobResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchExperimentJob, job_id)
        return _to_response(row) if row else None


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    current_stage: str | None = None,
    run_id: str | None = None,
    last_success_run_id: str | None = None,
    error_message: str | None = None,
    stage_update: tuple[str, str, str] | None = None,
) -> ExperimentJobResponse | None:
    """stage_update = (stage_name, stage_status, message)."""
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchExperimentJob, job_id)
        if not row:
            return None
        now = _utcnow()
        if status:
            row.status = status
            if status == "running" and not row.started_at:
                row.started_at = now
            if status in ("completed", "failed", "cancelled"):
                row.completed_at = now
        if current_stage is not None:
            row.current_stage = current_stage
        if run_id is not None:
            row.run_id = run_id
        if last_success_run_id is not None:
            row.last_success_run_id = last_success_run_id
        if error_message is not None:
            row.error_message = error_message

        if stage_update:
            stage_name, stage_status, message = stage_update
            stages = _parse_stages(row.stages_json or "[]")
            stage_map = {s.stage: s for s in stages}
            rec = stage_map.get(stage_name)  # type: ignore[arg-type]
            if rec:
                rec.status = stage_status  # type: ignore[assignment]
                rec.message = message
                if stage_status == "running" and not rec.started_at:
                    rec.started_at = now
                if stage_status in ("completed", "failed", "skipped"):
                    rec.completed_at = now
            row.stages_json = json_dumps([s.model_dump(mode="json") for s in stages])

        row.updated_at = now
        session.commit()
        session.refresh(row)
        return _to_response(row)


def mark_stage(job_id: str, stage: str, status: str = "running", message: str = "") -> None:
    update_job(job_id, current_stage=stage, stage_update=(stage, status, message))
    if status == "running":
        update_job(job_id, status="running")


def complete_stage(job_id: str, stage: str, message: str = "") -> None:
    update_job(job_id, stage_update=(stage, "completed", message))


def fail_job(job_id: str, stage: str, error: str, *, preserve_last_success: bool = True) -> None:
    job = get_job(job_id)
    last = job.last_success_run_id if job and preserve_last_success else None
    update_job(
        job_id,
        status="failed",
        current_stage="failed",
        error_message=error[:500],
        last_success_run_id=last,
        stage_update=(stage, "failed", error[:200]),
    )
