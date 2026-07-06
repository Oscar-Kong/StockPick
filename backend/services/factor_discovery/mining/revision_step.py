"""Bounded revision proposal validation for mining lineages."""
from __future__ import annotations

from engines.factor.discovery.compiler import compile_factor_expression
from engines.factor.discovery.parser import parse_factor_expression
from models.schemas_factor_discovery import formula_hash
from services.factor_discovery.mining.deduplication import MiningDeduplicationService
from services.factor_discovery.mining.errors import MiningRevisionPolicyError
from services.factor_discovery.mining.models import FactorMiningBudgetPolicy, FactorRevisionProposal
from services.factor_discovery.mining.repositories import FactorMiningEvaluationRepository
from services.factor_discovery.mining.revision_diff import diff_revision, validate_revision_policy


class MiningRevisionStep:
    def __init__(self) -> None:
        self._evaluations = FactorMiningEvaluationRepository()
        self._dedup = MiningDeduplicationService()

    def validate_proposal(
        self,
        proposal: FactorRevisionProposal,
        *,
        session_id: str,
        budget: FactorMiningBudgetPolicy,
    ) -> dict:
        if "forward_return" in proposal.proposed_dsl.lower():
            raise MiningRevisionPolicyError("OUTCOME_FIELD_FORBIDDEN", proposal.proposed_dsl)
        if any(token in proposal.proposed_dsl.lower() for token in ("import ", "def ", "select ", "python")):
            raise MiningRevisionPolicyError("CODE_INJECTION_FORBIDDEN", proposal.proposed_dsl)

        parsed = parse_factor_expression(proposal.proposed_dsl)
        compiled = compile_factor_expression(parsed)
        child_hash = formula_hash(parsed)
        if child_hash == proposal.parent_formula_hash:
            raise MiningRevisionPolicyError("REVISION_IDENTICAL", child_hash)

        parent_ast = None
        try:
            from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
            from services.research_json import json_loads

            parent = FactorLlmCandidateRepository().get(proposal.parent_formula_candidate_id)
            if parent:
                parent_dsl = json_loads(parent.candidate_json, {}).get("proposed_dsl") or json_loads(
                    parent.candidate_json, {}
                ).get("dsl")
                if parent_dsl:
                    parent_ast = parse_factor_expression(parent_dsl)
        except Exception:
            parent_ast = None

        diff = diff_revision(parent_ast, parsed) if parent_ast else None
        evaluated_hashes = {
            e.formula_hash
            for e in self._evaluations.list_for_lineage(session_id, proposal.lineage_id)
            if not e.is_duplicate
        }
        if diff:
            validate_revision_policy(diff, budget=budget, evaluated_hashes=evaluated_hashes)

        dup = self._dedup.check_formula_hash(
            session_id=session_id,
            lineage_id=proposal.lineage_id,
            formula_hash_value=child_hash,
            revision_round=proposal.revision_round,
        )
        if dup.is_duplicate:
            raise MiningRevisionPolicyError("REVISION_DUPLICATE", child_hash)

        return {
            "child_formula_hash": child_hash,
            "plan_hash": compiled.plan_hash,
            "ast_diff": diff.__dict__ if diff else None,
            "compile_meta": {
                "formula_hash": child_hash,
                "plan_hash": compiled.plan_hash,
            },
        }
