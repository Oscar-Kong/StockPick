"""Persistence for Factor Discovery LLM candidates."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from data.db_engine import get_engine
from engines.factor_discovery_models import FactorLlmCandidate
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FactorLlmCandidateRepository:
    def create(self, **fields: Any) -> str:
        cid = fields.pop("candidate_id", f"fdlcnd_{uuid.uuid4().hex[:12]}")
        content_hash = fields.get("candidate_content_hash")
        ctype = fields.get("candidate_type")
        if content_hash and ctype:
            existing = self.get_by_hash(content_hash, candidate_type=ctype)
            if existing:
                fields["duplicate_of_candidate_id"] = existing.candidate_id
        with Session(get_engine()) as session:
            session.add(FactorLlmCandidate(candidate_id=cid, **fields))
            session.commit()
        return cid

    def get(self, candidate_id: str) -> FactorLlmCandidate | None:
        with Session(get_engine()) as session:
            return session.get(FactorLlmCandidate, candidate_id)

    def get_by_hash(self, content_hash: str, *, candidate_type: str) -> FactorLlmCandidate | None:
        with Session(get_engine()) as session:
            return (
                session.query(FactorLlmCandidate)
                .filter(
                    FactorLlmCandidate.candidate_content_hash == content_hash,
                    FactorLlmCandidate.candidate_type == candidate_type,
                )
                .one_or_none()
            )

    def get_by_formula_hash(self, formula_hash: str) -> FactorLlmCandidate | None:
        with Session(get_engine()) as session:
            return (
                session.query(FactorLlmCandidate)
                .filter(FactorLlmCandidate.formula_hash == formula_hash, FactorLlmCandidate.candidate_type == "FORMULA")
                .one_or_none()
            )

    def update_review(
        self,
        candidate_id: str,
        *,
        review_status: str,
        reviewed_by: str,
        review_reason: str,
    ) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorLlmCandidate, candidate_id)
            if row is None:
                return
            row.review_status = review_status
            row.reviewed_by = reviewed_by
            row.review_reason = review_reason
            row.reviewed_at = _utcnow()
            session.commit()

    def list_for_family(
        self,
        research_family_id: str,
        *,
        candidate_type: str | None = None,
        review_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FactorLlmCandidate]:
        with Session(get_engine()) as session:
            q = session.query(FactorLlmCandidate).filter(
                FactorLlmCandidate.research_family_id == research_family_id
            )
            if candidate_type:
                q = q.filter(FactorLlmCandidate.candidate_type == candidate_type)
            if review_status:
                q = q.filter(FactorLlmCandidate.review_status == review_status)
            return q.order_by(FactorLlmCandidate.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def parse_json(row: FactorLlmCandidate) -> dict:
        return json_loads(row.candidate_json, {})
