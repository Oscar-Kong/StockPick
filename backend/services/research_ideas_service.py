"""Research ideas CRUD."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from data.db_engine import get_engine
from engines.quant_models import ResearchIdea
from models.schemas_research import (
    IdeaStatus,
    ResearchIdeaCreate,
    ResearchIdeaListResponse,
    ResearchIdeaResponse,
    ResearchIdeaUpdate,
)
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "new",
        "saved",
        "ready_to_test",
        "running",
        "supported",
        "rejected",
        "inconclusive",
        "archived",
    }
)

VALID_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        "factor_deterioration",
        "factor_improvement",
        "prediction_drift",
        "recommendation_calibration",
        "market_regime",
        "scan_dispersion",
        "portfolio_concentration",
        "pair_relationship",
        "data_quality",
        "failed_experiment",
        "user_created",
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_response(row: ResearchIdea) -> ResearchIdeaResponse:
    return ResearchIdeaResponse(
        id=row.id,
        title=row.title,
        hypothesis=row.hypothesis or "",
        description=row.description or "",
        why_now=row.why_now or "",
        source_type=row.source_type,  # type: ignore[arg-type]
        source_references=json_loads(row.source_references_json, []),
        sleeve=row.sleeve,
        universe_definition=json_loads(row.universe_definition_json, {}),
        suggested_experiment_type=row.suggested_experiment_type,  # type: ignore[arg-type]
        suggested_parameters=json_loads(row.suggested_parameters_json, {}),
        priority=int(row.priority or 50),
        confidence=float(row.confidence or 0.5),
        status=row.status,  # type: ignore[arg-type]
        user_notes=row.user_notes or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create_idea(body: ResearchIdeaCreate) -> ResearchIdeaResponse:
    if body.source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"invalid source_type: {body.source_type}")
    if body.status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {body.status}")

    idea_id = f"idea_{uuid.uuid4().hex[:12]}"
    now = _utcnow()
    engine = get_engine()
    with Session(engine) as session:
        row = ResearchIdea(
            id=idea_id,
            title=body.title.strip(),
            hypothesis=body.hypothesis,
            description=body.description,
            why_now=body.why_now,
            source_type=body.source_type,
            source_references_json=json_dumps(body.source_references),
            sleeve=body.sleeve,
            universe_definition_json=json_dumps(body.universe_definition),
            suggested_experiment_type=body.suggested_experiment_type,
            suggested_parameters_json=json_dumps(body.suggested_parameters),
            priority=body.priority,
            confidence=body.confidence,
            status=body.status,
            user_notes=body.user_notes,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_response(row)


def get_idea(idea_id: str) -> ResearchIdeaResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchIdea, idea_id)
        return _to_response(row) if row else None


def list_ideas(
    *,
    status: IdeaStatus | None = None,
    sleeve: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> ResearchIdeaListResponse:
    engine = get_engine()
    with Session(engine) as session:
        q = session.query(ResearchIdea)
        if status:
            q = q.filter(ResearchIdea.status == status)
        if sleeve:
            q = q.filter(ResearchIdea.sleeve == sleeve)
        total = q.count()
        rows = q.order_by(ResearchIdea.updated_at.desc()).offset(offset).limit(limit).all()
        return ResearchIdeaListResponse(
            ideas=[_to_response(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )


def update_idea(idea_id: str, body: ResearchIdeaUpdate) -> ResearchIdeaResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchIdea, idea_id)
        if not row:
            return None
        data = body.model_dump(exclude_unset=True)
        if "source_type" in data and data["source_type"] not in VALID_SOURCE_TYPES:
            raise ValueError(f"invalid source_type: {data['source_type']}")
        if "status" in data and data["status"] not in VALID_STATUSES:
            raise ValueError(f"invalid status: {data['status']}")
        if "title" in data and data["title"] is not None:
            row.title = data["title"].strip()
        for field in ("hypothesis", "description", "why_now", "sleeve", "user_notes"):
            if field in data:
                setattr(row, field, data[field])
        if "source_type" in data:
            row.source_type = data["source_type"]
        if "source_references" in data:
            row.source_references_json = json_dumps(data["source_references"])
        if "universe_definition" in data:
            row.universe_definition_json = json_dumps(data["universe_definition"])
        if "suggested_experiment_type" in data:
            row.suggested_experiment_type = data["suggested_experiment_type"]
        if "suggested_parameters" in data:
            row.suggested_parameters_json = json_dumps(data["suggested_parameters"])
        if "priority" in data:
            row.priority = data["priority"]
        if "confidence" in data:
            row.confidence = data["confidence"]
        if "status" in data:
            row.status = data["status"]
        row.updated_at = _utcnow()
        session.commit()
        session.refresh(row)
        return _to_response(row)


def delete_idea(idea_id: str) -> bool:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchIdea, idea_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
