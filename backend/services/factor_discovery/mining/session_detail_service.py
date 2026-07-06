"""Session detail and action availability for mining UI contracts."""
from __future__ import annotations

from services.factor_discovery.mining.budget_service import load_usage
from services.factor_discovery.mining.errors import MiningSessionNotFoundError
from services.factor_discovery.mining.models import (
    FactorMiningAutoPolicy,
    FactorMiningBudgetPolicy,
    FactorMiningPausePolicy,
    FactorMiningStoppingPolicy,
    LineageStatus,
    MiningSessionStatus,
    SessionActionDisabledReasons,
    SessionActionFlags,
)
from services.factor_discovery.mining.mutation_helpers import count_pending_reviews
from services.factor_discovery.mining.repositories import (
    FactorMiningEvaluationRepository,
    FactorMiningEventRepository,
    FactorMiningLineageRepository,
    FactorMiningSessionRepository,
)
from services.factor_discovery.mining.state_machine import TERMINAL_SESSION_STATES, is_lineage_active
from services.research_json import json_loads


class FactorMiningSessionDetailService:
    def __init__(self) -> None:
        self._sessions = FactorMiningSessionRepository()
        self._lineages = FactorMiningLineageRepository()
        self._evaluations = FactorMiningEvaluationRepository()
        self._events = FactorMiningEventRepository()

    def get_session_detail(self, session_id: str) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        lineages = self._lineages.list_for_session(session_id)
        evaluations = self._evaluations.list_for_session(session_id)
        events = self._events.list_for_session(session_id)
        usage = load_usage(row.usage_json)
        budget = FactorMiningBudgetPolicy.model_validate(json_loads(row.budget_policy_json, {}))
        actions, disabled = self._action_flags(row.status, row.session_mode)
        pending = count_pending_reviews(session_id, status=row.status)
        pending_total = pending["hypotheses"] + pending["formulas"] + pending["revisions"]
        promising_count = sum(
            1 for l in lineages if l.status == LineageStatus.PROMISING_FOR_HUMAN_REVIEW.value
        )
        normalized = json_loads(row.normalized_request_json, {})
        return {
            "session_id": session_id,
            "session_name": normalized.get("session_name") or normalized.get("research_objective", "")[:80],
            "status": row.status,
            "session_mode": row.session_mode,
            "state_version": row.state_version,
            "pause_reason": row.pause_reason,
            "terminal_reason": row.terminal_reason,
            "research_objective": row.research_objective,
            "research_family_id": row.research_family_id,
            "data_provider_id": row.data_provider_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": (row.paused_at or row.started_at or row.created_at).isoformat()
            if (row.paused_at or row.started_at or row.created_at)
            else None,
            "immutable_config": {
                "session_config_hash": row.session_config_hash,
                "budget_hash": row.budget_hash,
                "period_hash": row.period_hash,
                "validation_config_hash": row.validation_config_hash,
                "snapshot_id": row.snapshot_id,
                "primary_horizon_sessions": row.primary_horizon_sessions,
            },
            "policies": {
                "pause": json_loads(row.pause_policy_json, {}),
                "stopping": json_loads(row.stopping_policy_json, {}),
                "auto": json_loads(row.auto_policy_json, {}),
            },
            "budget": budget.model_dump(mode="json"),
            "usage": usage.model_dump(),
            "budget_remaining": {
                "formulas_evaluated": max(0, budget.max_formulas_reaching_evaluation - usage.formulas_evaluated),
                "revision_rounds": max(0, budget.max_total_revision_attempts - usage.revision_rounds),
                "llm_interactions": max(0, budget.max_llm_interactions - usage.llm_interactions),
            },
            "lineages": [
                {
                    "lineage_id": l.lineage_id,
                    "status": l.status,
                    "revision_depth": l.revision_depth,
                    "root_formula_hash": l.root_formula_hash,
                    "terminal_reason": l.terminal_reason,
                    "origin_hypothesis_candidate_id": l.origin_hypothesis_candidate_id,
                    "current_formula_candidate_id": l.current_formula_candidate_id,
                    "best_artifact_id": l.best_artifact_id,
                }
                for l in lineages
            ],
            "evaluations": [
                {
                    "evaluation_id": e.evaluation_id,
                    "lineage_id": e.lineage_id,
                    "run_id": e.run_id,
                    "artifact_id": e.artifact_id,
                    "formula_hash": e.formula_hash,
                    "revision_round": e.revision_round,
                    "is_duplicate": e.is_duplicate,
                }
                for e in evaluations
            ],
            "pending_approval_count": pending_total,
            "pending_reviews": pending,
            "promising_candidate_count": promising_count,
            "active_lineage_count": sum(1 for l in lineages if is_lineage_active(l.status)),
            "recent_events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "previous_state": e.previous_state,
                    "new_state": e.new_state,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events[-20:]
            ],
            "allowed_actions": actions.model_dump(),
            "action_disabled_reasons": disabled.model_dump(exclude_none=True),
            "integrity_status": "not_verified",
            "no_sealed_access": True,
            "no_lifecycle_promotion": True,
        }

    def _action_flags(self, status: str, mode: str) -> tuple[SessionActionFlags, SessionActionDisabledReasons]:
        terminal = status in {s.value for s in TERMINAL_SESSION_STATES}
        disabled = SessionActionDisabledReasons()

        can_authorize = status == MiningSessionStatus.AWAITING_AUTHORIZATION.value
        can_start = status == MiningSessionStatus.AUTHORIZED.value
        can_advance = not terminal and status != MiningSessionStatus.PAUSED.value
        can_pause = not terminal and status != MiningSessionStatus.PAUSED.value
        can_resume = status == MiningSessionStatus.PAUSED.value
        can_cancel = not terminal
        can_approve_hypothesis = status in {
            MiningSessionStatus.AWAITING_HYPOTHESIS_REVIEW.value,
            MiningSessionStatus.PAUSED.value,
        }
        can_reject_hypothesis = can_approve_hypothesis
        can_approve_formula = status in {
            MiningSessionStatus.AWAITING_FORMULA_REVIEW.value,
            MiningSessionStatus.PAUSED.value,
        }
        can_reject_formula = can_approve_formula
        can_approve_revision = status in {
            MiningSessionStatus.AWAITING_REVISION_REVIEW.value,
            MiningSessionStatus.PAUSED.value,
        }
        can_reject_revision = can_approve_revision

        if terminal:
            msg = f"Session is terminal ({status})"
            disabled.can_authorize = msg
            disabled.can_start = msg
            disabled.can_advance = msg
            disabled.can_pause = msg
            disabled.can_resume = msg
            disabled.can_cancel = msg
        elif status == MiningSessionStatus.PAUSED.value:
            disabled.can_advance = "Session is paused — resume first"
            disabled.can_pause = "Session is already paused"
        if not can_authorize:
            disabled.can_authorize = disabled.can_authorize or f"Status is {status}"
        if not can_start:
            disabled.can_start = disabled.can_start or f"Status is {status}, expected AUTHORIZED"
        if not can_approve_hypothesis:
            disabled.can_approve_hypothesis = f"Status is {status}"
            disabled.can_reject_hypothesis = disabled.can_approve_hypothesis
        if not can_approve_formula:
            disabled.can_approve_formula = f"Status is {status}"
            disabled.can_reject_formula = disabled.can_approve_formula
        if not can_approve_revision:
            disabled.can_approve_revision = f"Status is {status}"
            disabled.can_reject_revision = disabled.can_approve_revision

        actions = SessionActionFlags(
            can_authorize=can_authorize,
            can_start=can_start,
            can_advance=can_advance,
            can_pause=can_pause,
            can_resume=can_resume,
            can_cancel=can_cancel,
            can_approve_hypothesis=can_approve_hypothesis,
            can_reject_hypothesis=can_reject_hypothesis,
            can_approve_formula=can_approve_formula,
            can_reject_formula=can_reject_formula,
            can_approve_revision=can_approve_revision,
            can_reject_revision=can_reject_revision,
        )
        return actions, disabled

    def mutation_envelope(
        self,
        session_id: str,
        *,
        prior_status: str | None = None,
        events_created: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> dict:
        detail = self.get_session_detail(session_id)
        return {
            "session_id": session_id,
            "prior_status": prior_status,
            "status": detail["status"],
            "state_version": detail["state_version"],
            "pause_reason": detail["pause_reason"],
            "stop_reason": detail["terminal_reason"],
            "pending_reviews": detail["pending_reviews"],
            "active_lineage_count": detail["active_lineage_count"],
            "budget_summary": detail["budget_remaining"],
            "allowed_actions": detail["allowed_actions"],
            "action_disabled_reasons": detail.get("action_disabled_reasons", {}),
            "events_created": events_created or [],
            "warnings": warnings or [],
        }
