"""Hypothesis critique via schema-constrained LLM."""
from __future__ import annotations

import json

from services.factor_discovery.llm.capabilities import require_llm_operation
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.client import get_factor_discovery_llm_client
from services.factor_discovery.llm.field_catalog import available_fields_for_llm
from services.factor_discovery.llm.hashing import canonical_hash, text_hash
from services.factor_discovery.llm.interaction_repository import FactorLlmInteractionRepository
from services.factor_discovery.llm.models import (
    CandidateType,
    FactorLlmRequestMetadata,
    HypothesisCritiqueResult,
    LlmOperationType,
    ReviewStatus,
)
from services.factor_discovery.llm.prompt_registry import get_template
from services.factor_discovery.llm.validators import validate_hypothesis_candidate
from services.research_json import json_dumps, json_loads


class FactorHypothesisCriticService:
    def __init__(self, *, llm_client=None) -> None:
        self._llm = llm_client or get_factor_discovery_llm_client()
        self._interactions = FactorLlmInteractionRepository()
        self._candidates = FactorLlmCandidateRepository()

    def critique(self, candidate_id: str, *, actor: str = "api") -> dict:
        require_llm_operation(LlmOperationType.HYPOTHESIS_CRITIQUE)
        row = self._candidates.get(candidate_id)
        if row is None or row.candidate_type != CandidateType.HYPOTHESIS.value:
            raise ValueError("hypothesis candidate not found")
        cand_data = json_loads(row.candidate_json, {})
        from services.factor_discovery.llm.models import GeneratedFactorHypothesisCandidate

        candidate = GeneratedFactorHypothesisCandidate.model_validate(
            {k: v for k, v in cand_data.items() if k != "validation_status"}
        )
        det_status = validate_hypothesis_candidate(candidate)

        template = get_template("factor_hypothesis_critic_v1")
        user_prompt = json.dumps(
            {
                "hypothesis": candidate.model_dump(mode="json"),
                "deterministic_validation_status": det_status.value,
                "available_fields": available_fields_for_llm(),
            },
            indent=2,
        )
        meta = FactorLlmRequestMetadata(
            operation_type=LlmOperationType.HYPOTHESIS_CRITIQUE,
            actor=actor,
            research_family_id=row.research_family_id,
        )
        iid = self._interactions.create(
            operation_type=LlmOperationType.HYPOTHESIS_CRITIQUE.value,
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
        try:
            response = self._llm.generate_structured(
                system_prompt=template.system_prompt,
                user_prompt=user_prompt,
                response_schema=HypothesisCritiqueResult,
                request_metadata=meta,
            )
            critique: HypothesisCritiqueResult = response.parsed  # type: ignore[assignment]
            if det_status.value in {"INVALID", "UNSUPPORTED_DATA"} and critique.recommended_decision == "CONTINUE_TO_FORMULA":
                critique = critique.model_copy(update={"recommended_decision": "REJECT"})
            content_hash = canonical_hash(critique.model_dump(mode="json"))
            cid = self._candidates.create(
                interaction_id=iid,
                research_family_id=row.research_family_id,
                hypothesis_candidate_id=candidate_id,
                candidate_type=CandidateType.CRITIQUE.value,
                candidate_sequence=1,
                candidate_json=json_dumps(critique.model_dump(mode="json")),
                candidate_content_hash=content_hash,
                review_status=ReviewStatus.PENDING_REVIEW.value,
            )
            self._interactions.complete(
                iid,
                status="COMPLETED",
                model_id=response.model_id,
                structured_output_hash=content_hash,
                finish_reason=response.finish_reason,
            )
            return {"interaction_id": iid, "critique_candidate_id": cid}
        except Exception as exc:
            code = getattr(exc, "code", "CRITIQUE_FAILED")
            self._interactions.fail(iid, error_code=code, error_summary=str(exc)[:500])
            raise
