"""Create immutable FactorDefinition from approved LLM formula candidate."""
from __future__ import annotations

import re

from engines.factor.discovery.parser import parse_factor_expression
from models.schemas_factor_discovery import FactorDefinition, FactorDirection, FactorLifecycleStatus
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.errors import FactorLlmReviewConflictError
from services.factor_discovery.llm.models import ReviewStatus
from services.factor_discovery.repositories import FactorDefinitionRepository
from services.research_json import json_loads


def _slug_factor_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    return slug[:48] or "factor_llm"


class FactorDefinitionFromLlmService:
    def create_definition(
        self,
        formula_candidate_id: str,
        *,
        factor_id: str | None,
        version: str,
        actor: str,
        reason: str,
    ) -> dict:
        if not reason.strip():
            raise FactorLlmReviewConflictError("MISSING_REASON", "reason required")
        row = FactorLlmCandidateRepository().get(formula_candidate_id)
        if row is None or row.candidate_type != "FORMULA":
            raise FactorLlmReviewConflictError("CANDIDATE_NOT_FOUND", formula_candidate_id)
        if row.review_status != ReviewStatus.APPROVED.value:
            raise FactorLlmReviewConflictError("FORMULA_NOT_APPROVED", row.review_status)
        if row.validation_status != "COMPILED_FOR_REVIEW":
            raise FactorLlmReviewConflictError("FORMULA_NOT_COMPILED", row.validation_status or "")
        data = json_loads(row.candidate_json, {})
        meta = data.get("compile_meta", {})
        canonical_dsl = meta.get("canonical_dsl") or data.get("canonical_dsl")
        if not canonical_dsl:
            raise FactorLlmReviewConflictError("MISSING_CANONICAL_DSL", formula_candidate_id)
        ast = parse_factor_expression(canonical_dsl)
        fid = factor_id or _slug_factor_id(data.get("proposed_factor_name", "factor"))
        definition = FactorDefinition(
            factor_id=fid,
            version=version,
            display_name=data.get("proposed_factor_name", fid),
            expression=ast,
            expected_direction=FactorDirection(data.get("expected_direction", "HIGHER_IS_BETTER")),
            intended_universe="research",
            rebalance_frequency="monthly",
            holding_period_sessions=21,
            lifecycle_status=FactorLifecycleStatus.DRAFT,
        )
        FactorDefinitionRepository().create_version(
            definition,
            created_by=actor,
            canonical_dsl=canonical_dsl,
            canonical_ast=definition.expression.model_dump(mode="json"),
        )
        return {
            "factor_id": fid,
            "version": version,
            "formula_hash": definition.formula_hash(),
            "lifecycle_status": FactorLifecycleStatus.DRAFT.value,
            "formula_candidate_id": formula_candidate_id,
        }
