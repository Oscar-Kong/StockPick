"""Formula review LLM operation after deterministic compilation."""
from __future__ import annotations

import json

from services.factor_discovery.llm.capabilities import require_llm_operation
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.client import get_factor_discovery_llm_client
from services.factor_discovery.llm.hashing import canonical_hash, text_hash
from services.factor_discovery.llm.interaction_repository import FactorLlmInteractionRepository
from services.factor_discovery.llm.models import (
    CandidateType,
    FactorLlmRequestMetadata,
    FormulaReviewResult,
    LlmOperationType,
    ReviewStatus,
)
from services.factor_discovery.llm.prompt_registry import get_template
from services.research_json import json_dumps, json_loads


class FactorFormulaReviewService:
    def __init__(self, *, llm_client=None) -> None:
        self._llm = llm_client or get_factor_discovery_llm_client()
        self._interactions = FactorLlmInteractionRepository()
        self._candidates = FactorLlmCandidateRepository()

    def review(self, formula_candidate_id: str, *, actor: str = "api") -> dict:
        require_llm_operation(LlmOperationType.FORMULA_REVIEW)
        row = self._candidates.get(formula_candidate_id)
        if row is None or row.candidate_type != CandidateType.FORMULA.value:
            raise ValueError("formula candidate not found")
        data = json_loads(row.candidate_json, {})
        if data.get("compile_status") != "COMPILED_FOR_REVIEW":
            from services.factor_discovery.llm.errors import FactorLlmReviewConflictError

            raise FactorLlmReviewConflictError("FORMULA_NOT_COMPILED", data.get("compile_status", ""))

        template = get_template("factor_formula_reviewer_v1")
        user_prompt = json.dumps(
            {
                "formula": data,
                "compiler_required_fields": data.get("compile_meta", {}).get("required_fields", []),
            },
            indent=2,
        )
        meta = FactorLlmRequestMetadata(operation_type=LlmOperationType.FORMULA_REVIEW, actor=actor)
        iid = self._interactions.create(
            operation_type=LlmOperationType.FORMULA_REVIEW.value,
            research_family_id=row.research_family_id,
            provider_id=getattr(self._llm, "provider_id", "unknown"),
            model_id="pending",
            prompt_template_id=template.template_id,
            prompt_template_version=template.version,
            system_prompt_hash=text_hash(template.system_prompt),
            user_prompt_hash=text_hash(user_prompt),
            response_schema_version="factor-llm-v1",
            status="RUNNING",
            actor=actor,
        )
        response = self._llm.generate_structured(
            system_prompt=template.system_prompt,
            user_prompt=user_prompt,
            response_schema=FormulaReviewResult,
            request_metadata=meta,
        )
        review: FormulaReviewResult = response.parsed  # type: ignore[assignment]
        content_hash = canonical_hash(review.model_dump(mode="json"))
        cid = self._candidates.create(
            interaction_id=iid,
            research_family_id=row.research_family_id,
            hypothesis_candidate_id=row.hypothesis_candidate_id,
            candidate_type=CandidateType.CRITIQUE.value,
            candidate_sequence=1,
            candidate_json=json_dumps(review.model_dump(mode="json")),
            candidate_content_hash=content_hash,
            review_status=ReviewStatus.PENDING_REVIEW.value,
        )
        self._interactions.complete(iid, status="COMPLETED", model_id=response.model_id)
        return {"interaction_id": iid, "review_candidate_id": cid, "suggested_decision": review.suggested_decision}
