"""Human review gates for Factor Discovery LLM candidates."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from data.db_engine import get_engine
from engines.factor_discovery_models import FactorLlmReviewEvent
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.errors import FactorLlmReviewConflictError
from services.factor_discovery.llm.models import ReviewStatus
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FactorLlmReviewService:
    def __init__(self) -> None:
        self._candidates = FactorLlmCandidateRepository()

    def approve_hypothesis(self, candidate_id: str, *, actor: str, reason: str) -> None:
        self._transition(candidate_id, actor=actor, reason=reason, target=ReviewStatus.APPROVED)

    def reject_hypothesis(self, candidate_id: str, *, actor: str, reason: str) -> None:
        self._transition(candidate_id, actor=actor, reason=reason, target=ReviewStatus.REJECTED)

    def approve_formula(self, candidate_id: str, *, actor: str, reason: str) -> None:
        row = self._candidates.get(candidate_id)
        if row is None or row.candidate_type != "FORMULA":
            raise FactorLlmReviewConflictError("CANDIDATE_NOT_FOUND", candidate_id)
        if row.validation_status != "COMPILED_FOR_REVIEW":
            raise FactorLlmReviewConflictError("FORMULA_NOT_COMPILED", row.validation_status or "")
        self._transition(candidate_id, actor=actor, reason=reason, target=ReviewStatus.APPROVED)

    def reject_formula(self, candidate_id: str, *, actor: str, reason: str) -> None:
        self._transition(candidate_id, actor=actor, reason=reason, target=ReviewStatus.REJECTED)

    def _transition(self, candidate_id: str, *, actor: str, reason: str, target: ReviewStatus) -> None:
        if not actor or actor == "llm":
            raise FactorLlmReviewConflictError("INVALID_ACTOR", "human actor required")
        if not reason.strip():
            raise FactorLlmReviewConflictError("MISSING_REASON", "review reason required")
        row = self._candidates.get(candidate_id)
        if row is None:
            raise FactorLlmReviewConflictError("CANDIDATE_NOT_FOUND", candidate_id)
        if row.review_status != ReviewStatus.PENDING_REVIEW.value:
            raise FactorLlmReviewConflictError("INVALID_REVIEW_STATE", row.review_status)
        prev = row.review_status
        self._candidates.update_review(candidate_id, review_status=target.value, reviewed_by=actor, review_reason=reason)
        with Session(get_engine()) as session:
            session.add(
                FactorLlmReviewEvent(
                    review_event_id=f"fdlrev_{uuid.uuid4().hex[:12]}",
                    candidate_id=candidate_id,
                    previous_status=prev,
                    new_status=target.value,
                    actor=actor,
                    reason=reason,
                )
            )
            session.commit()
