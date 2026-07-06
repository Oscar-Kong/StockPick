"""Persistence for Factor Discovery LLM interactions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from data.db_engine import get_engine
from engines.factor_discovery_models import FactorLlmInteraction
from services.factor_discovery.llm.errors import FactorLlmIdempotencyConflictError
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FactorLlmInteractionRepository:
    def create(self, **fields: Any) -> str:
        iid = fields.pop("interaction_id", f"fdllm_{uuid.uuid4().hex[:12]}")
        idem = fields.get("idempotency_key")
        payload_hash = fields.get("request_payload_hash")
        if idem:
            existing = self.get_by_idempotency(idem)
            if existing:
                if payload_hash and existing.request_payload_hash and existing.request_payload_hash != payload_hash:
                    raise FactorLlmIdempotencyConflictError(
                        "IDEMPOTENCY_PAYLOAD_MISMATCH", f"idempotency key {idem} reused"
                    )
                return existing.interaction_id
        with Session(get_engine()) as session:
            session.add(FactorLlmInteraction(interaction_id=iid, **fields))
            session.commit()
        return iid

    def complete(self, interaction_id: str, **fields: Any) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorLlmInteraction, interaction_id)
            if row is None:
                return
            for k, v in fields.items():
                setattr(row, k, v)
            row.completed_at = _utcnow()
            session.commit()

    def fail(self, interaction_id: str, *, error_code: str, error_summary: str) -> None:
        self.complete(interaction_id, status="FAILED", error_code=error_code, error_summary=error_summary[:500])

    def get(self, interaction_id: str) -> FactorLlmInteraction | None:
        with Session(get_engine()) as session:
            return session.get(FactorLlmInteraction, interaction_id)

    def get_by_idempotency(self, key: str) -> FactorLlmInteraction | None:
        with Session(get_engine()) as session:
            return session.query(FactorLlmInteraction).filter(FactorLlmInteraction.idempotency_key == key).one_or_none()

    def list_candidates_filter(
        self,
        *,
        research_family_id: str | None = None,
        candidate_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FactorLlmInteraction]:
        with Session(get_engine()) as session:
            q = session.query(FactorLlmInteraction).order_by(FactorLlmInteraction.created_at.desc())
            if research_family_id:
                q = q.filter(FactorLlmInteraction.research_family_id == research_family_id)
            if candidate_type:
                q = q.filter(FactorLlmInteraction.operation_type == candidate_type)
            return q.offset(offset).limit(limit).all()
