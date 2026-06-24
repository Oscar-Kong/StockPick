"""Results index actions — archive, notes, duplicate experiment, follow-up ideas."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from data.db_engine import get_engine
from engines.quant_models import ResearchExperiment, ResearchRunIndex
from models.schemas_research import (
    ResearchExperimentCreate,
    ResearchIdeaCreate,
    ResearchRunDuplicateExperimentResponse,
    ResearchRunListItem,
    ResearchRunSummary,
)
from services.research_experiments_service import create_experiment, get_experiment
from services.research_ideas_service import create_idea
from services.research_run_service import _row_to_list_item, get_run, index_run_from_store
from sqlalchemy.orm import Session

_EXPERIMENT_TYPE_MAP = {
    "walk_forward": "walk_forward",
    "factor_ic_panel": "factor_validation",
    "prediction_outcomes": "prediction_calibration",
    "pairs": "pairs_discovery",
    "similar_signal": "similar_signal",
    "portfolio_policy": "portfolio_policy",
    "quant_job": "factor_validation",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def archive_run(run_id: str, *, archived: bool = True) -> ResearchRunListItem | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchRunIndex, run_id)
        if not row:
            summary = get_run(run_id)
            if not summary:
                return None
            index_run_from_store(run_id)
            row = session.get(ResearchRunIndex, run_id)
        if not row:
            return None
        row.archived = 1 if archived else 0
        row.updated_at = _utcnow()
        session.commit()
        session.refresh(row)
        return _row_to_list_item(row)


def set_run_notes(run_id: str, notes: str) -> ResearchRunListItem | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchRunIndex, run_id)
        if not row:
            return None
        row.research_notes = notes or ""
        row.updated_at = _utcnow()
        session.commit()
        session.refresh(row)
        return _row_to_list_item(row)


def duplicate_experiment_from_run(run_id: str) -> ResearchRunDuplicateExperimentResponse | None:
    summary = get_run(run_id)
    if not summary:
        return None
    exp_type = _EXPERIMENT_TYPE_MAP.get(summary.run_type, "factor_validation")
    source_exp = get_experiment(summary.experiment_id) if summary.experiment_id else None
    name = f"Copy — {summary.name}"[:256]
    exp = create_experiment(
        ResearchExperimentCreate(
            idea_id=summary.idea_id or (source_exp.idea_id if source_exp else None),
            name=name,
            experiment_type=exp_type,  # type: ignore[arg-type]
            hypothesis=source_exp.hypothesis if source_exp else "",
            sleeve=summary.sleeve,
            universe_definition={"symbols": summary.universe} if summary.universe else {},
            parameters=dict(summary.parameters),
            preset=source_exp.preset if source_exp else "standard_research",  # type: ignore[arg-type]
            notes=f"Duplicated from run {run_id}",
        )
    )
    return ResearchRunDuplicateExperimentResponse(experiment_id=exp.id, run_id=run_id)


def create_follow_up_idea(
    run_id: str,
    *,
    title: str | None = None,
    hypothesis: str = "",
) -> ResearchRunSummary | None:
    summary = get_run(run_id)
    if not summary:
        return None
    idea = create_idea(
        ResearchIdeaCreate(
            title=title or f"Follow-up: {summary.name}"[:256],
            hypothesis=hypothesis or f"Follow-up investigation after run {run_id}",
            source_type="failed_experiment" if summary.status == "failed" else "user_created",
            source_references=[run_id],
            sleeve=summary.sleeve,
            suggested_experiment_type=_EXPERIMENT_TYPE_MAP.get(summary.run_type),  # type: ignore[arg-type]
            suggested_parameters=dict(summary.parameters),
            status="new",
        )
    )
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchRunIndex, run_id)
        if row:
            row.idea_id = idea.id
            row.updated_at = _utcnow()
            session.commit()
    refreshed = get_run(run_id)
    return refreshed
