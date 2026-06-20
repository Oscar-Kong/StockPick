"""Reviewable change proposals — no automatic production updates."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from data.db_engine import get_engine
from engines.quant_models import ChangeProposal
from models.schemas_research import (
    ChangeProposalCreate,
    ChangeProposalListResponse,
    ChangeProposalResponse,
    ChangeProposalUpdate,
    ProposalStatus,
)
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "needs_validation",
        "ready_for_review",
        "rejected",
        "approved_for_staging",
        "archived",
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_response(row: ChangeProposal) -> ChangeProposalResponse:
    return ChangeProposalResponse(
        id=row.id,
        title=row.title,
        finding=row.finding or "",
        supporting_run_ids=json_loads(row.supporting_run_ids_json, []),
        proposed_change=json_loads(row.proposed_change_json, {}),
        affected_sleeve=row.affected_sleeve,
        affected_factors=json_loads(row.affected_factors_json, []),
        expected_benefit=row.expected_benefit or "",
        main_risks=row.main_risks or "",
        required_validation=row.required_validation or "",
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create_proposal(body: ChangeProposalCreate) -> ChangeProposalResponse:
    if body.status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {body.status}")

    proposal_id = f"cp_{uuid.uuid4().hex[:12]}"
    now = _utcnow()
    engine = get_engine()
    with Session(engine) as session:
        row = ChangeProposal(
            id=proposal_id,
            title=body.title.strip(),
            finding=body.finding,
            supporting_run_ids_json=json_dumps(body.supporting_run_ids),
            proposed_change_json=json_dumps(body.proposed_change),
            affected_sleeve=body.affected_sleeve,
            affected_factors_json=json_dumps(body.affected_factors),
            expected_benefit=body.expected_benefit,
            main_risks=body.main_risks,
            required_validation=body.required_validation,
            status=body.status,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_response(row)


def get_proposal(proposal_id: str) -> ChangeProposalResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ChangeProposal, proposal_id)
        return _to_response(row) if row else None


def list_proposals(
    *,
    status: ProposalStatus | None = None,
    affected_sleeve: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> ChangeProposalListResponse:
    engine = get_engine()
    with Session(engine) as session:
        q = session.query(ChangeProposal)
        if status:
            q = q.filter(ChangeProposal.status == status)
        if affected_sleeve:
            q = q.filter(ChangeProposal.affected_sleeve == affected_sleeve)
        total = q.count()
        rows = q.order_by(ChangeProposal.updated_at.desc()).offset(offset).limit(limit).all()
        return ChangeProposalListResponse(
            proposals=[_to_response(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )


def update_proposal(proposal_id: str, body: ChangeProposalUpdate) -> ChangeProposalResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ChangeProposal, proposal_id)
        if not row:
            return None
        data = body.model_dump(exclude_unset=True)
        if "status" in data and data["status"] not in VALID_STATUSES:
            raise ValueError(f"invalid status: {data['status']}")
        if "title" in data and data["title"] is not None:
            row.title = data["title"].strip()
        for field in ("finding", "affected_sleeve", "expected_benefit", "main_risks", "required_validation"):
            if field in data:
                setattr(row, field, data[field])
        if "supporting_run_ids" in data:
            row.supporting_run_ids_json = json_dumps(data["supporting_run_ids"])
        if "proposed_change" in data:
            row.proposed_change_json = json_dumps(data["proposed_change"])
        if "affected_factors" in data:
            row.affected_factors_json = json_dumps(data["affected_factors"])
        if "status" in data:
            row.status = data["status"]
        row.updated_at = _utcnow()
        session.commit()
        session.refresh(row)
        return _to_response(row)


def delete_proposal(proposal_id: str) -> bool:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ChangeProposal, proposal_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
