"""Session lifecycle: create, authorize, pause, resume, cancel."""
from __future__ import annotations

from datetime import datetime, timezone

from engines.factor.discovery.validation_hashing import validation_config_hash
from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities
from services.factor_discovery.llm.request_normalizer import normalize_research_request
from services.factor_discovery.llm.review_service import FactorLlmReviewService
from services.factor_discovery.mining.budget_service import load_usage
from services.factor_discovery.mining.errors import (
    MiningSessionAuthorizationError,
    MiningSessionNotFoundError,
    MiningSessionStateError,
)
from services.factor_discovery.mining.hashing import (
    budget_policy_hash,
    pause_policy_hash,
    period_hash,
    session_config_hash,
    stopping_policy_hash,
)
from services.factor_discovery.mining.models import (
    FactorMiningAutoPolicy,
    FactorMiningBudgetPolicy,
    FactorMiningPausePolicy,
    FactorMiningSessionCreateRequest,
    FactorMiningStoppingPolicy,
    MiningSessionMode,
    MiningSessionStatus,
    PauseTrigger,
)
from services.factor_discovery.mining.policies import require_mining_capabilities, validate_session_mode
from services.factor_discovery.mining.repositories import (
    FactorMiningEventRepository,
    FactorMiningSessionRepository,
)
from services.factor_discovery.mining.state_machine import default_pause_policy_for_mode, validate_session_transition
from services.factor_discovery.mining.mutation_helpers import assert_state_version
from services.factor_discovery.mining.session_detail_service import FactorMiningSessionDetailService
from services.factor_discovery.repositories import FactorDataSnapshotRepository, FactorResearchFamilyRepository
from services.research_json import json_dumps, json_loads


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _default_budget() -> FactorMiningBudgetPolicy:
    from config import (
        FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_EVALUATED_FORMULAS,
        FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_REVISION_ROUNDS,
        FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_VALIDATION_EXPOSURES,
    )

    return FactorMiningBudgetPolicy(
        max_formulas_reaching_evaluation=FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_EVALUATED_FORMULAS,
        max_revision_rounds_per_lineage=FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_REVISION_ROUNDS,
        max_validation_exposures_per_lineage=FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_VALIDATION_EXPOSURES,
    )


class FactorMiningSessionService:
    def __init__(self) -> None:
        self._sessions = FactorMiningSessionRepository()
        self._events = FactorMiningEventRepository()
        self._families = FactorResearchFamilyRepository()
        self._snapshots = FactorDataSnapshotRepository()
        self._review = FactorLlmReviewService()
        self._detail = FactorMiningSessionDetailService()

    def _envelope(self, session_id: str, *, prior_status: str | None = None, events: list[str] | None = None) -> dict:
        return self._detail.mutation_envelope(session_id, prior_status=prior_status, events_created=events)

    def create_session(self, req: FactorMiningSessionCreateRequest) -> dict:
        validate_session_mode(req.session_mode.value)
        family = self._families.get(req.research_family_id)
        if family is None:
            raise MiningSessionAuthorizationError("FAMILY_NOT_FOUND", req.research_family_id)
        if family.closed:
            raise MiningSessionAuthorizationError("FAMILY_CLOSED", req.research_family_id)

        normalized = normalize_research_request(req.research_request, research_family_id=req.research_family_id)
        pause = req.pause_policy or FactorMiningPausePolicy(
            triggers=[PauseTrigger(t) for t in default_pause_policy_for_mode(req.session_mode.value)]
        )
        stopping = req.stopping_policy or FactorMiningStoppingPolicy()
        budget = req.budget_policy or _default_budget()
        auto = req.auto_policy or FactorMiningAutoPolicy()

        snapshot_identity = None
        if req.snapshot_id:
            snap = self._snapshots.get(req.snapshot_id)
            if snap is None:
                raise MiningSessionAuthorizationError("SNAPSHOT_NOT_FOUND", req.snapshot_id)
            snapshot_identity = snap.snapshot_identity_hash

        ph = period_hash(req.period_split)
        vhash = validation_config_hash(req.validation_config)
        cfg_hash = session_config_hash(
            research_family_id=req.research_family_id,
            normalized_request=normalized,
            session_mode=req.session_mode.value,
            snapshot_id=req.snapshot_id,
            snapshot_identity_hash=snapshot_identity,
            data_provider_id=req.data_provider_id,
            data_source_policy_id=req.data_source_policy_id,
            period_split=req.period_split,
            validation_config=req.validation_config,
            pause_policy=pause,
            stopping_policy=stopping,
            budget_policy=budget,
            auto_policy=auto,
        )

        sid = self._sessions.create(
            research_family_id=req.research_family_id,
            research_objective=normalized.research_objective,
            normalized_request_json=json_dumps(normalized.model_dump(mode="json")),
            session_mode=req.session_mode.value,
            status=MiningSessionStatus.AWAITING_AUTHORIZATION.value,
            actor=req.actor,
            snapshot_id=req.snapshot_id,
            snapshot_identity_hash=snapshot_identity,
            data_provider_id=req.data_provider_id,
            data_source_policy_id=req.data_source_policy_id,
            period_split_json=json_dumps(req.period_split.model_dump(mode="json")),
            period_hash=ph,
            validation_config_json=json_dumps(req.validation_config.model_dump(mode="json")),
            validation_config_hash=vhash,
            primary_horizon_sessions=req.validation_config.primary_horizon_sessions,
            pause_policy_json=json_dumps(pause.model_dump(mode="json")),
            pause_policy_hash=pause_policy_hash(pause),
            stopping_policy_json=json_dumps(stopping.model_dump(mode="json")),
            stopping_policy_hash=stopping_policy_hash(stopping),
            budget_policy_json=json_dumps(budget.model_dump(mode="json")),
            budget_hash=budget_policy_hash(budget),
            session_config_hash=cfg_hash,
            auto_policy_json=json_dumps(auto.model_dump(mode="json")),
        )
        self._events.append(
            session_id=sid,
            event_type="SESSION_CREATED",
            actor_type="human",
            actor_identifier=req.actor,
            new_state=MiningSessionStatus.AWAITING_AUTHORIZATION.value,
            safe_summary="mining session created",
        )
        return {"session_id": sid, "status": MiningSessionStatus.AWAITING_AUTHORIZATION.value, "state_version": 0}

    def authorize_session(self, session_id: str, *, actor: str, reason: str, state_version: int) -> dict:
        require_mining_capabilities()
        if not reason.strip():
            raise MiningSessionAuthorizationError("MISSING_REASON", "authorization reason required")
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        prior = row.status
        validate_session_transition(MiningSessionStatus(row.status), MiningSessionStatus.AUTHORIZED)

        caps = assess_historical_store_capabilities()
        if not caps.price_research_available and row.data_provider_id == "historical_store":
            raise MiningSessionAuthorizationError("PROVIDER_NOT_READY", ";".join(caps.blocking_reasons))

        self._sessions.transition(
            session_id,
            new_status=MiningSessionStatus.AUTHORIZED.value,
            expected_version=state_version,
            authorization_reason=reason,
            authorized_at=_utcnow(),
        )
        self._events.append(
            session_id=session_id,
            event_type="SESSION_AUTHORIZED",
            actor_type="human",
            actor_identifier=actor,
            previous_state=prior,
            new_state=MiningSessionStatus.AUTHORIZED.value,
            reason_code="AUTHORIZED",
            safe_summary=reason[:500],
        )
        return self._envelope(session_id, prior_status=prior, events=["SESSION_AUTHORIZED"])

    def start_session(self, session_id: str, *, actor: str, state_version: int) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        if row.status != MiningSessionStatus.AUTHORIZED.value:
            raise MiningSessionStateError("SESSION_NOT_AUTHORIZED", row.status)
        prior = row.status
        self._sessions.transition(
            session_id,
            new_status=MiningSessionStatus.GENERATING_HYPOTHESES.value,
            expected_version=state_version,
            started_at=_utcnow(),
        )
        self._events.append(
            session_id=session_id,
            event_type="SESSION_STARTED",
            actor_type="human",
            actor_identifier=actor,
            previous_state=prior,
            new_state=MiningSessionStatus.GENERATING_HYPOTHESES.value,
        )
        return self._envelope(session_id, prior_status=prior, events=["SESSION_STARTED"])

    def pause_session(self, session_id: str, *, actor: str, reason: str, state_version: int) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        prior = row.status
        self._sessions.transition(
            session_id,
            new_status=MiningSessionStatus.PAUSED.value,
            expected_version=state_version,
            paused_at=_utcnow(),
            pause_reason=reason[:500],
        )
        self._events.append(
            session_id=session_id,
            event_type="SESSION_PAUSED",
            actor_type="human",
            actor_identifier=actor,
            previous_state=prior,
            new_state=MiningSessionStatus.PAUSED.value,
            safe_summary=reason[:500],
        )
        return self._envelope(session_id, prior_status=prior, events=["SESSION_PAUSED"])

    def resume_session(self, session_id: str, *, actor: str, resume_to: str, state_version: int) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        if row.status != MiningSessionStatus.PAUSED.value:
            raise MiningSessionStateError("SESSION_NOT_PAUSED", row.status)
        prior = row.status
        self._sessions.transition(
            session_id,
            new_status=resume_to,
            expected_version=state_version,
            paused_at=None,
            pause_reason=None,
        )
        self._events.append(
            session_id=session_id,
            event_type="SESSION_RESUMED",
            actor_type="human",
            actor_identifier=actor,
            previous_state=prior,
            new_state=resume_to,
        )
        return self._envelope(session_id, prior_status=prior, events=["SESSION_RESUMED"])

    def cancel_session(self, session_id: str, *, actor: str, reason: str, state_version: int) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        prior = row.status
        self._sessions.transition(
            session_id,
            new_status=MiningSessionStatus.CANCELLED.value,
            expected_version=state_version,
            cancelled_at=_utcnow(),
            terminal_reason=reason[:500],
        )
        self._events.append(
            session_id=session_id,
            event_type="SESSION_CANCELLED",
            actor_type="human",
            actor_identifier=actor,
            previous_state=prior,
            new_state=MiningSessionStatus.CANCELLED.value,
            safe_summary=reason[:500],
        )
        return self._envelope(session_id, prior_status=prior, events=["SESSION_CANCELLED"])

    def approve_hypothesis(self, session_id: str, candidate_id: str, *, actor: str, reason: str, state_version: int) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        prior = row.status
        assert_state_version(session_id, state_version)
        self._review.approve_hypothesis(candidate_id, actor=actor, reason=reason)
        usage = load_usage(row.usage_json)
        from services.factor_discovery.mining.budget_service import reserve_usage

        usage = reserve_usage(usage, "hypothesis_approved")
        self._sessions.update_usage(session_id, usage.model_dump())
        return self._envelope(session_id, prior_status=prior, events=["HYPOTHESIS_APPROVED"])

    def reject_hypothesis(self, session_id: str, candidate_id: str, *, actor: str, reason: str, state_version: int) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        prior = row.status
        assert_state_version(session_id, state_version)
        self._review.reject_hypothesis(candidate_id, actor=actor, reason=reason)
        return self._envelope(session_id, prior_status=prior, events=["HYPOTHESIS_REJECTED"])

    def approve_formula(self, session_id: str, candidate_id: str, *, actor: str, reason: str, state_version: int) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        prior = row.status
        assert_state_version(session_id, state_version)
        self._review.approve_formula(candidate_id, actor=actor, reason=reason)
        return self._envelope(session_id, prior_status=prior, events=["FORMULA_APPROVED"])

    def reject_formula(self, session_id: str, candidate_id: str, *, actor: str, reason: str, state_version: int) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        prior = row.status
        assert_state_version(session_id, state_version)
        self._review.reject_formula(candidate_id, actor=actor, reason=reason)
        return self._envelope(session_id, prior_status=prior, events=["FORMULA_REJECTED"])

    def approve_revision(
        self,
        session_id: str,
        candidate_id: str,
        *,
        actor: str,
        reason: str,
        state_version: int,
    ) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        if row.status in {
            MiningSessionStatus.COMPLETED.value,
            MiningSessionStatus.CANCELLED.value,
            MiningSessionStatus.BUDGET_EXHAUSTED.value,
            MiningSessionStatus.FAILED.value,
        }:
            raise MiningSessionStateError("SESSION_TERMINAL", row.status)
        prior = row.status
        assert_state_version(session_id, state_version)
        self._review.approve_formula(candidate_id, actor=actor, reason=reason)
        usage = load_usage(row.usage_json)
        from services.factor_discovery.mining.budget_service import reserve_usage
        from services.factor_discovery.mining.repositories import FactorMiningLineageRepository

        usage = reserve_usage(usage, "revision")
        self._sessions.update_usage(session_id, usage.model_dump())
        for lin in FactorMiningLineageRepository().list_for_session(session_id):
            if lin.current_formula_candidate_id == candidate_id:
                FactorMiningLineageRepository().update(lin.lineage_id, status="REVISION_APPROVED")
        return self._envelope(session_id, prior_status=prior, events=["REVISION_APPROVED"])

    def reject_revision(
        self,
        session_id: str,
        candidate_id: str,
        *,
        actor: str,
        reason: str,
        state_version: int,
    ) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        prior = row.status
        assert_state_version(session_id, state_version)
        self._review.reject_formula(candidate_id, actor=actor, reason=reason)
        return self._envelope(session_id, prior_status=prior, events=["REVISION_REJECTED"])

    def get_session(self, session_id: str) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        return {
            "session_id": row.session_id,
            "status": row.status,
            "session_mode": row.session_mode,
            "state_version": row.state_version,
            "research_family_id": row.research_family_id,
            "usage": json_loads(row.usage_json, {}),
        }
