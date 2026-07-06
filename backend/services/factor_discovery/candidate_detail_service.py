"""UI-ready candidate detail contracts for Factor Discovery review."""
from __future__ import annotations

from data.db_engine import get_engine
from engines.factor_discovery_models import FactorLlmReviewEvent, FactorMiningRevisionProposal
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.models import CandidateType, ReviewStatus
from services.factor_discovery.mining.repositories import FactorMiningLineageRepository, FactorMiningSessionRepository
from services.factor_discovery.mining.session_detail_service import FactorMiningSessionDetailService
from services.research_json import json_loads
from sqlalchemy.orm import Session


class FactorCandidateDetailService:
    def __init__(self) -> None:
        self._candidates = FactorLlmCandidateRepository()
        self._sessions = FactorMiningSessionRepository()
        self._lineages = FactorMiningLineageRepository()
        self._detail = FactorMiningSessionDetailService()

    def _review_events(self, candidate_id: str) -> list[dict]:
        with Session(get_engine()) as session:
            rows = (
                session.query(FactorLlmReviewEvent)
                .filter(FactorLlmReviewEvent.candidate_id == candidate_id)
                .order_by(FactorLlmReviewEvent.created_at.asc())
                .all()
            )
        return [
            {
                "review_event_id": r.review_event_id,
                "previous_status": r.previous_status,
                "new_status": r.new_status,
                "actor": r.actor,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def _session_for_candidate(self, candidate_id: str) -> tuple[str | None, int | None]:
        for row in self._sessions.list_sessions(limit=200):
            for lin in self._lineages.list_for_session(row.session_id):
                if lin.origin_hypothesis_candidate_id == candidate_id or lin.current_formula_candidate_id == candidate_id:
                    return row.session_id, row.state_version
        return None, None

    def _allowed_review(self, session_id: str | None, review_type: str) -> dict:
        if not session_id:
            return {"can_approve": False, "can_reject": False}
        detail = self._detail.get_session_detail(session_id)
        actions = detail["allowed_actions"]
        if review_type == "hypothesis":
            return {
                "can_approve": actions.get("can_approve_hypothesis", False),
                "can_reject": actions.get("can_reject_hypothesis", False),
            }
        if review_type == "formula":
            return {
                "can_approve": actions.get("can_approve_formula", False),
                "can_reject": actions.get("can_reject_formula", False),
            }
        return {
            "can_approve": actions.get("can_approve_revision", False),
            "can_reject": actions.get("can_reject_revision", False),
        }

    def _critique_for(self, hypothesis_id: str) -> dict | None:
        with Session(get_engine()) as session:
            from engines.factor_discovery_models import FactorLlmCandidate

            row = (
                session.query(FactorLlmCandidate)
                .filter(
                    FactorLlmCandidate.hypothesis_candidate_id == hypothesis_id,
                    FactorLlmCandidate.candidate_type == CandidateType.CRITIQUE.value,
                )
                .order_by(FactorLlmCandidate.created_at.desc())
                .first()
            )
        if row is None:
            return None
        data = json_loads(row.candidate_json, {})
        return {
            "critique_candidate_id": row.candidate_id,
            "interaction_id": row.interaction_id,
            "summary": data,
        }

    def get_hypothesis_detail(self, candidate_id: str) -> dict:
        row = self._candidates.get(candidate_id)
        if row is None or row.candidate_type != CandidateType.HYPOTHESIS.value:
            raise FactorDiscoveryError("CANDIDATE_NOT_FOUND", candidate_id)
        data = json_loads(row.candidate_json, {})
        session_id, state_version = self._session_for_candidate(candidate_id)
        critique = self._critique_for(candidate_id)
        return {
            "candidate_id": candidate_id,
            "candidate_type": "HYPOTHESIS",
            "interaction_id": row.interaction_id,
            "session_id": session_id,
            "state_version": state_version,
            "research_family_id": row.research_family_id,
            "candidate_name": data.get("candidate_name"),
            "economic_rationale": data.get("economic_rationale"),
            "expected_mechanism": data.get("expected_mechanism"),
            "expected_direction": data.get("expected_direction"),
            "intended_universe": data.get("intended_universe"),
            "holding_period_sessions": data.get("expected_holding_period_sessions"),
            "rebalance_frequency": data.get("rebalance_frequency"),
            "required_data_classes": data.get("required_data_classes", []),
            "proposed_fields": data.get("proposed_fields", []),
            "deterministic_support_status": data.get("validation_status"),
            "provider_capability_status": data.get("provider_capability_status"),
            "known_risks": data.get("known_risks", []),
            "expected_failure_conditions": data.get("expected_failure_conditions", []),
            "expected_turnover": data.get("expected_turnover"),
            "benchmark_overlap": data.get("potential_factor_overlap"),
            "assumptions": data.get("assumptions", []),
            "critique": critique,
            "review_status": row.review_status,
            "review_events": self._review_events(candidate_id),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "allowed_actions": self._allowed_review(session_id, "hypothesis"),
            "no_sealed_access": True,
            "no_lifecycle_promotion": True,
        }

    def get_formula_detail(self, candidate_id: str) -> dict:
        row = self._candidates.get(candidate_id)
        if row is None or row.candidate_type != CandidateType.FORMULA.value:
            raise FactorDiscoveryError("CANDIDATE_NOT_FOUND", candidate_id)
        data = json_loads(row.candidate_json, {})
        session_id, state_version = self._session_for_candidate(candidate_id)
        compile_meta = data.get("compile_meta", {})
        ast = compile_meta.get("canonical_ast") or data.get("canonical_ast")
        return {
            "candidate_id": candidate_id,
            "candidate_type": "FORMULA",
            "parent_hypothesis_id": row.hypothesis_candidate_id,
            "interaction_id": row.interaction_id,
            "session_id": session_id,
            "state_version": state_version,
            "research_family_id": row.research_family_id,
            "proposed_factor_name": data.get("proposed_factor_name") or data.get("factor_name"),
            "original_llm_dsl": data.get("original_dsl") or data.get("proposed_dsl"),
            "canonical_dsl": data.get("canonical_dsl"),
            "dsl_version": data.get("dsl_version", "factor-dsl-v1"),
            "formula_hash": row.formula_hash or data.get("formula_hash"),
            "plan_hash": compile_meta.get("plan_hash") or data.get("plan_hash"),
            "expected_direction": data.get("expected_direction"),
            "compiler_required_fields": compile_meta.get("required_fields", []),
            "llm_declared_fields": data.get("required_fields", []),
            "field_mismatch": compile_meta.get("field_mismatch"),
            "maximum_lookback": compile_meta.get("max_lookback"),
            "maximum_lag": compile_meta.get("max_lag"),
            "operators_used": compile_meta.get("operators_used", []),
            "ast_node_count": compile_meta.get("node_count"),
            "ast_depth": compile_meta.get("depth"),
            "cross_sectional_required": compile_meta.get("cross_sectional_required", False),
            "time_series_required": compile_meta.get("time_series_required", True),
            "pit_required": compile_meta.get("pit_required", False),
            "adjusted_price_required": compile_meta.get("adjusted_price_required", True),
            "data_source_policy": compile_meta.get("data_source_policy_id"),
            "compiler_warnings": compile_meta.get("warnings", []),
            "compile_error": data.get("compile_error"),
            "compile_status": data.get("compile_status") or row.validation_status,
            "formula_review": self._critique_for(candidate_id),
            "canonical_ast": ast,
            "review_status": row.review_status,
            "review_events": self._review_events(candidate_id),
            "duplicate_status": "duplicate" if row.duplicate_of_candidate_id else "unique",
            "duplicate_of": row.duplicate_of_candidate_id,
            "linked_definition_id": row.linked_definition_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "allowed_actions": self._allowed_review(session_id, "formula"),
            "no_sealed_access": True,
        }

    def get_revision_detail(self, candidate_id: str) -> dict:
        row = self._candidates.get(candidate_id)
        if row is None:
            raise FactorDiscoveryError("CANDIDATE_NOT_FOUND", candidate_id)
        session_id, state_version = self._session_for_candidate(candidate_id)
        with Session(get_engine()) as session:
            proposal = (
                session.query(FactorMiningRevisionProposal)
                .filter(FactorMiningRevisionProposal.child_formula_candidate_id == candidate_id)
                .one_or_none()
            )
        parent_data: dict = {}
        child_data = json_loads(row.candidate_json, {})
        if proposal:
            parent_row = self._candidates.get(proposal.parent_formula_candidate_id)
            if parent_row:
                parent_data = json_loads(parent_row.candidate_json, {})
        diff = json_loads(proposal.ast_diff_json, {}) if proposal and proposal.ast_diff_json else {}
        proposal_json = json_loads(proposal.proposal_json, {}) if proposal else {}
        return {
            "candidate_id": candidate_id,
            "candidate_type": "REVISION",
            "session_id": session_id,
            "state_version": state_version,
            "lineage_id": proposal.lineage_id if proposal else None,
            "parent_formula_candidate_id": proposal.parent_formula_candidate_id if proposal else None,
            "parent_formula_hash": proposal.parent_formula_hash if proposal else None,
            "proposed_formula_hash": proposal.child_formula_hash if proposal else row.formula_hash,
            "parent_canonical_dsl": parent_data.get("canonical_dsl"),
            "proposed_canonical_dsl": child_data.get("canonical_dsl"),
            "revision_round": proposal.revision_round if proposal else None,
            "failure_categories_addressed": proposal_json.get("failure_categories_addressed", []),
            "revision_rationale": proposal_json.get("revision_rationale"),
            "expected_semantic_change": proposal_json.get("expected_semantic_change"),
            "expected_turnover_change": proposal_json.get("expected_turnover_direction"),
            "semantic_diff": diff,
            "fields_added": diff.get("fields_added", []),
            "fields_removed": diff.get("fields_removed", []),
            "operators_added": diff.get("operators_added", []),
            "operators_removed": diff.get("operators_removed", []),
            "window_changes": diff.get("window_changes", []),
            "lag_changes": diff.get("lag_changes", []),
            "constant_changes": diff.get("constant_changes", []),
            "neutralization_changes": diff.get("neutralization_changes", []),
            "node_count_delta": diff.get("node_delta"),
            "depth_delta": diff.get("depth_delta"),
            "lookback_delta": diff.get("lookback_delta"),
            "structural_similarity": diff.get("semantic_classification"),
            "exact_duplicate": diff.get("exact_duplicate", False),
            "near_duplicate": diff.get("near_duplicate", False),
            "revision_policy_rules": diff.get("policy_rules", []),
            "policy_result": proposal.policy_status if proposal else None,
            "review_status": row.review_status,
            "review_events": self._review_events(candidate_id),
            "linked_revised_definition_id": row.linked_definition_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "allowed_actions": self._allowed_review(session_id, "revision"),
            "no_sealed_access": True,
        }
