"""Shared mutation helpers for mining session API contracts."""
from __future__ import annotations

from typing import Any

from services.factor_discovery.mining.errors import MiningConcurrencyConflictError, MiningSessionStateError
from services.factor_discovery.mining.models import LineageStatus, MiningSessionStatus
from services.factor_discovery.mining.repositories import FactorMiningLineageRepository, FactorMiningSessionRepository


def parse_expected_state_version(body: dict[str, Any]) -> int:
    """Require optimistic-concurrency version on mining mutations."""
    if "expected_state_version" in body and body["expected_state_version"] is not None:
        return int(body["expected_state_version"])
    if "state_version" in body and body["state_version"] is not None:
        return int(body["state_version"])
    raise MiningSessionStateError("MISSING_STATE_VERSION", "expected_state_version is required")


def assert_state_version(session_id: str, expected: int) -> None:
    row = FactorMiningSessionRepository().get(session_id)
    if row is None:
        from services.factor_discovery.mining.errors import MiningSessionNotFoundError

        raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
    if row.state_version != expected:
        raise MiningConcurrencyConflictError(
            "STATE_VERSION_CONFLICT",
            f"expected {expected}, got {row.state_version}",
        )


def count_pending_reviews(session_id: str, *, status: str) -> dict[str, int]:
    lineages = FactorMiningLineageRepository().list_for_session(session_id)
    formulas = sum(1 for l in lineages if l.status == LineageStatus.FORMULA_REVIEW_PENDING.value)
    revisions = sum(1 for l in lineages if l.status == LineageStatus.REVISION_REVIEW_PENDING.value)
    hypotheses = 1 if status == MiningSessionStatus.AWAITING_HYPOTHESIS_REVIEW.value else 0
    return {"hypotheses": hypotheses, "formulas": formulas, "revisions": revisions}


def mining_http_status_for_error(code: str) -> int:
    if code == "STATE_VERSION_CONFLICT":
        return 409
    if code in {"MISSING_STATE_VERSION", "MISSING_REASON", "INVALID_REVIEW_STATE"}:
        return 422
    if code in {"SESSION_NOT_FOUND", "CANDIDATE_NOT_FOUND"}:
        return 404
    if code in {"FACTOR_DISCOVERY_LOOP_DISABLED", "FACTOR_DISCOVERY_DISABLED", "FACTOR_DISCOVERY_LLM_DISABLED"}:
        return 503
    return 400
