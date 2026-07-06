"""Research experiment definitions — separate from runs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from data.db_engine import get_engine
from engines.quant_models import ResearchExperiment
from models.schemas_research import (
    ExperimentType,
    ResearchExperimentCreate,
    ResearchExperimentListResponse,
    ResearchExperimentResponse,
    ResearchExperimentUpdate,
)
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session

VALID_EXPERIMENT_TYPES: frozenset[str] = frozenset(
    {
        "factor_validation",
        "walk_forward",
        "prediction_calibration",
        "pairs_discovery",
        "similar_signal",
        "portfolio_policy",
        "scan_evaluation",
        "factor_discovery",
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_response(row: ResearchExperiment) -> ResearchExperimentResponse:
    return ResearchExperimentResponse(
        id=row.id,
        idea_id=row.idea_id,
        name=row.name,
        experiment_type=row.experiment_type,  # type: ignore[arg-type]
        hypothesis=row.hypothesis or "",
        null_hypothesis=row.null_hypothesis or "",
        success_criteria=row.success_criteria or "",
        failure_criteria=row.failure_criteria or "",
        sleeve=row.sleeve,
        universe_definition=json_loads(row.universe_definition_json, {}),
        parameters=json_loads(row.parameters_json, {}),
        preset=row.preset,  # type: ignore[arg-type]
        notes=row.notes or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create_experiment(body: ResearchExperimentCreate) -> ResearchExperimentResponse:
    if body.experiment_type not in VALID_EXPERIMENT_TYPES:
        raise ValueError(f"invalid experiment_type: {body.experiment_type}")

    exp_id = f"exp_{uuid.uuid4().hex[:12]}"
    now = _utcnow()
    engine = get_engine()
    with Session(engine) as session:
        row = ResearchExperiment(
            id=exp_id,
            idea_id=body.idea_id,
            name=body.name.strip(),
            experiment_type=body.experiment_type,
            hypothesis=body.hypothesis,
            null_hypothesis=body.null_hypothesis,
            success_criteria=body.success_criteria,
            failure_criteria=body.failure_criteria,
            sleeve=body.sleeve,
            universe_definition_json=json_dumps(body.universe_definition),
            parameters_json=json_dumps(body.parameters),
            preset=body.preset,
            notes=body.notes,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_response(row)


def get_experiment(experiment_id: str) -> ResearchExperimentResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchExperiment, experiment_id)
        return _to_response(row) if row else None


def list_experiments(
    *,
    idea_id: str | None = None,
    experiment_type: ExperimentType | None = None,
    sleeve: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> ResearchExperimentListResponse:
    engine = get_engine()
    with Session(engine) as session:
        q = session.query(ResearchExperiment)
        if idea_id:
            q = q.filter(ResearchExperiment.idea_id == idea_id)
        if experiment_type:
            q = q.filter(ResearchExperiment.experiment_type == experiment_type)
        if sleeve:
            q = q.filter(ResearchExperiment.sleeve == sleeve)
        total = q.count()
        rows = q.order_by(ResearchExperiment.updated_at.desc()).offset(offset).limit(limit).all()
        return ResearchExperimentListResponse(
            experiments=[_to_response(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )


def update_experiment(experiment_id: str, body: ResearchExperimentUpdate) -> ResearchExperimentResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchExperiment, experiment_id)
        if not row:
            return None
        data = body.model_dump(exclude_unset=True)
        if "experiment_type" in data and data["experiment_type"] not in VALID_EXPERIMENT_TYPES:
            raise ValueError(f"invalid experiment_type: {data['experiment_type']}")
        if "name" in data and data["name"] is not None:
            row.name = data["name"].strip()
        for field in (
            "idea_id",
            "hypothesis",
            "null_hypothesis",
            "success_criteria",
            "failure_criteria",
            "sleeve",
            "preset",
            "notes",
        ):
            if field in data:
                setattr(row, field, data[field])
        if "experiment_type" in data:
            row.experiment_type = data["experiment_type"]
        if "universe_definition" in data:
            row.universe_definition_json = json_dumps(data["universe_definition"])
        if "parameters" in data:
            row.parameters_json = json_dumps(data["parameters"])
        row.updated_at = _utcnow()
        session.commit()
        session.refresh(row)
        return _to_response(row)


def delete_experiment(experiment_id: str) -> bool:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchExperiment, experiment_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
