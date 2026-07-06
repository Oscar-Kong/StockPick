"""Bounded revision proposal generation for mining lineages."""
from __future__ import annotations

import re

from engines.factor.discovery.parser import parse_factor_expression
from models.schemas_factor_discovery import formula_hash
from services.factor_discovery.mining.models import (
    BOUNDED_REVISION_POLICY_VERSION,
    FailureCategory,
    FactorMiningBudgetPolicy,
    FactorRevisionProposal,
)
from services.factor_discovery.mining.repositories import FactorMiningRevisionProposalRepository
from services.factor_discovery.mining.revision_step import MiningRevisionStep
from services.research_json import json_dumps, json_loads


_SLOWER_LOOKBACK_MAP = {
    "return_21d": "return_63d",
    "return_63d": "return_126d",
    "return_126d": "return_252d",
}


class MiningRevisionGenerationService:
    def __init__(self) -> None:
        self._proposals = FactorMiningRevisionProposalRepository()
        self._validator = MiningRevisionStep()

    def propose_from_categories(
        self,
        *,
        session_id: str,
        lineage_id: str,
        parent_candidate_id: str,
        parent_dsl: str,
        parent_formula_hash: str,
        revision_round: int,
        categories: list[FailureCategory],
        budget: FactorMiningBudgetPolicy,
    ) -> dict:
        proposed_dsl = self._derive_dsl(parent_dsl, categories)
        proposal = FactorRevisionProposal(
            parent_formula_candidate_id=parent_candidate_id,
            parent_formula_hash=parent_formula_hash,
            lineage_id=lineage_id,
            revision_round=revision_round,
            failure_categories_addressed=[c for c in categories if c in {FailureCategory.HIGH_TURNOVER, FailureCategory.WEAK_RANK_IC}],
            revision_rationale="Deterministic bounded revision from active failure categories.",
            proposed_dsl=proposed_dsl,
            expected_semantic_change="Slower lookback within supported fields.",
            expected_turnover_direction="decrease",
            required_fields=self._fields_from_dsl(proposed_dsl),
        )
        validation = self._validator.validate_proposal(proposal, session_id=session_id, budget=budget)
        pid = self._proposals.create(
            session_id=session_id,
            lineage_id=lineage_id,
            parent_formula_candidate_id=parent_candidate_id,
            parent_formula_hash=parent_formula_hash,
            child_formula_hash=validation["child_formula_hash"],
            revision_round=revision_round,
            proposal_json=json_dumps(proposal.model_dump(mode="json")),
            ast_diff_json=json_dumps(validation.get("ast_diff") or {}),
            policy_version=BOUNDED_REVISION_POLICY_VERSION,
            policy_status="PASS",
        )
        return {"proposal_id": pid, "proposal": proposal.model_dump(mode="json"), "validation": validation}

    def _derive_dsl(self, parent_dsl: str, categories: list[FailureCategory]) -> str:
        if FailureCategory.HIGH_TURNOVER in categories:
            for src, dst in _SLOWER_LOOKBACK_MAP.items():
                if src in parent_dsl:
                    return parent_dsl.replace(src, dst)
        m = re.search(r"return_\d+d", parent_dsl)
        if m and FailureCategory.WEAK_RANK_IC in categories:
            return parent_dsl.replace(m.group(0), "return_126d")
        if "rank(" in parent_dsl:
            return parent_dsl
        return f"rank({parent_dsl})"

    def _fields_from_dsl(self, dsl: str) -> list[str]:
        try:
            ast = parse_factor_expression(dsl)
            from models.schemas_factor_discovery import collect_field_ids

            return sorted(collect_field_ids(ast))
        except Exception:
            return []
