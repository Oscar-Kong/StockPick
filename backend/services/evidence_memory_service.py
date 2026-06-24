"""Stock-specific evidence memory — associations without duplicating price history."""
from __future__ import annotations

from datetime import datetime, timezone

from data.db_engine import get_engine
from engines.quant_models import EvidenceMemory
from models.schemas_research import (
    ConfirmationStatus,
    EvidenceImpact,
    EvidenceMemoryCreate,
    EvidenceMemoryListResponse,
    EvidenceMemoryResponse,
    EvidenceMemoryUpdate,
)
from services.evidence_impact_policy import evaluate_evidence_impact
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session

VALID_CONFIRMATION: frozenset[str] = frozenset(
    {"pending", "confirmed", "contradicted", "expired", "inconclusive"}
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_response(row: EvidenceMemory) -> EvidenceMemoryResponse:
    return EvidenceMemoryResponse(
        id=row.id,
        symbol=row.symbol,
        universe=json_loads(row.universe_json, None),
        original_signal=json_loads(row.original_signal_json, {}),
        factor_snapshot_ref=json_loads(row.factor_snapshot_ref_json, {}),
        market_regime=row.market_regime,
        experiment_id=row.experiment_id,
        run_id=row.run_id,
        deterministic_finding=row.deterministic_finding or "",
        verdict=row.verdict,
        evidence_impact=row.evidence_impact,  # type: ignore[arg-type]
        reliability=json_loads(row.reliability_json, None),
        forward_outcomes=json_loads(row.forward_outcomes_json, {}),
        confirmation_status=row.confirmation_status,  # type: ignore[arg-type]
        related_decisions=json_loads(row.related_decisions_json, []),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create_evidence_memory(body: EvidenceMemoryCreate) -> EvidenceMemoryResponse:
    if body.confirmation_status not in VALID_CONFIRMATION:
        raise ValueError(f"invalid confirmation_status: {body.confirmation_status}")

    evaluation = evaluate_evidence_impact(proposed_impact=body.evidence_impact)
    now = _utcnow()
    engine = get_engine()
    with Session(engine) as session:
        row = EvidenceMemory(
            symbol=body.symbol,
            universe_json=json_dumps(body.universe) if body.universe is not None else None,
            original_signal_json=json_dumps(body.original_signal),
            factor_snapshot_ref_json=json_dumps(body.factor_snapshot_ref),
            market_regime=body.market_regime,
            experiment_id=body.experiment_id,
            run_id=body.run_id,
            deterministic_finding=body.deterministic_finding,
            verdict=body.verdict,
            evidence_impact=evaluation.impact_level,
            reliability_json=json_dumps(body.reliability) if body.reliability else None,
            forward_outcomes_json=json_dumps(body.forward_outcomes),
            confirmation_status=body.confirmation_status,
            related_decisions_json=json_dumps(body.related_decisions),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_response(row)


def get_evidence_memory(memory_id: int) -> EvidenceMemoryResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(EvidenceMemory, memory_id)
        return _to_response(row) if row else None


def list_evidence_memory(
    *,
    symbol: str | None = None,
    run_id: str | None = None,
    experiment_id: str | None = None,
    evidence_impact: EvidenceImpact | None = None,
    offset: int = 0,
    limit: int = 50,
) -> EvidenceMemoryListResponse:
    engine = get_engine()
    with Session(engine) as session:
        q = session.query(EvidenceMemory)
        if symbol:
            q = q.filter(EvidenceMemory.symbol == symbol.upper())
        if run_id:
            q = q.filter(EvidenceMemory.run_id == run_id)
        if experiment_id:
            q = q.filter(EvidenceMemory.experiment_id == experiment_id)
        if evidence_impact:
            q = q.filter(EvidenceMemory.evidence_impact == evidence_impact)
        total = q.count()
        rows = q.order_by(EvidenceMemory.updated_at.desc()).offset(offset).limit(limit).all()
        return EvidenceMemoryListResponse(
            items=[_to_response(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )


def update_evidence_memory(memory_id: int, body: EvidenceMemoryUpdate) -> EvidenceMemoryResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(EvidenceMemory, memory_id)
        if not row:
            return None
        data = body.model_dump(exclude_unset=True)
        if "confirmation_status" in data and data["confirmation_status"] not in VALID_CONFIRMATION:
            raise ValueError(f"invalid confirmation_status: {data['confirmation_status']}")
        if "symbol" in data:
            row.symbol = data["symbol"].upper() if data["symbol"] else None
        if "universe" in data:
            row.universe_json = json_dumps(data["universe"]) if data["universe"] is not None else None
        if "original_signal" in data:
            row.original_signal_json = json_dumps(data["original_signal"])
        if "factor_snapshot_ref" in data:
            row.factor_snapshot_ref_json = json_dumps(data["factor_snapshot_ref"])
        for field in ("market_regime", "experiment_id", "run_id", "deterministic_finding", "verdict"):
            if field in data:
                setattr(row, field, data[field])
        if "evidence_impact" in data:
            evaluation = evaluate_evidence_impact(proposed_impact=data["evidence_impact"])
            row.evidence_impact = evaluation.impact_level
        if "reliability" in data:
            row.reliability_json = json_dumps(data["reliability"]) if data["reliability"] else None
        if "forward_outcomes" in data:
            row.forward_outcomes_json = json_dumps(data["forward_outcomes"])
        if "confirmation_status" in data:
            row.confirmation_status = data["confirmation_status"]
        if "related_decisions" in data:
            row.related_decisions_json = json_dumps(data["related_decisions"])
        row.updated_at = _utcnow()
        session.commit()
        session.refresh(row)
        return _to_response(row)


def delete_evidence_memory(memory_id: int) -> bool:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(EvidenceMemory, memory_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
