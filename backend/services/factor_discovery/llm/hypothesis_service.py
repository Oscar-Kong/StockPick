"""Hypothesis generation via schema-constrained LLM."""
from __future__ import annotations

import json
import uuid

from services.factor_discovery.llm.budgets import enforce_candidate_limit, enforce_daily_family_budget
from services.factor_discovery.llm.capabilities import require_llm_operation
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.client import get_factor_discovery_llm_client
from services.factor_discovery.llm.errors import FactorLlmCandidateValidationError
from services.factor_discovery.llm.field_catalog import available_fields_for_llm, unavailable_fields_for_llm
from services.factor_discovery.llm.hashing import canonical_hash, text_hash
from services.factor_discovery.llm.interaction_repository import FactorLlmInteractionRepository
from services.factor_discovery.llm.models import (
    CandidateType,
    FactorLlmRequestMetadata,
    FactorResearchRequest,
    GeneratedFactorHypothesisBatch,
    LlmOperationType,
    ReviewStatus,
)
from services.factor_discovery.llm.prompt_registry import get_template
from services.factor_discovery.llm.request_normalizer import normalize_research_request
from services.factor_discovery.llm.validators import normalize_candidate_name, validate_hypothesis_candidate
from services.research_json import json_dumps


class FactorHypothesisGenerationService:
    def __init__(self, *, llm_client=None) -> None:
        self._llm = llm_client or get_factor_discovery_llm_client()
        self._interactions = FactorLlmInteractionRepository()
        self._candidates = FactorLlmCandidateRepository()

    def generate(
        self,
        req: FactorResearchRequest,
        *,
        research_family_id: str,
        idempotency_key: str | None = None,
    ) -> dict:
        require_llm_operation(LlmOperationType.HYPOTHESIS_GENERATE)
        enforce_daily_family_budget(research_family_id=research_family_id, operation=LlmOperationType.HYPOTHESIS_GENERATE)
        normalized = normalize_research_request(req, research_family_id=research_family_id)
        enforce_candidate_limit(normalized.candidate_count, operation="hypothesis")

        template = get_template("factor_hypothesis_generator_v1")
        payload_hash = canonical_hash({"req": normalized.model_dump(), "family": research_family_id})
        if idempotency_key:
            existing = self._interactions.get_by_idempotency(idempotency_key)
            if existing:
                return {"interaction_id": existing.interaction_id, "duplicate": True}

        user_prompt = json.dumps(
            {
                "normalized_request": normalized.model_dump(mode="json"),
                "available_fields": available_fields_for_llm(),
                "unavailable_fields": unavailable_fields_for_llm(),
                "max_candidates": normalized.candidate_count,
                "user_objective": req.research_objective,
            },
            indent=2,
        )
        meta = FactorLlmRequestMetadata(
            operation_type=LlmOperationType.HYPOTHESIS_GENERATE,
            actor=req.actor,
            research_family_id=research_family_id,
            idempotency_key=idempotency_key,
        )
        iid = self._interactions.create(
            operation_type=LlmOperationType.HYPOTHESIS_GENERATE.value,
            research_family_id=research_family_id,
            provider_id=getattr(self._llm, "provider_id", "unknown"),
            model_id="pending",
            prompt_template_id=template.template_id,
            prompt_template_version=template.version,
            system_prompt_hash=text_hash(template.system_prompt),
            user_prompt_hash=text_hash(user_prompt),
            structured_input_hash=payload_hash,
            response_schema_version="factor-llm-v1",
            status="RUNNING",
            idempotency_key=idempotency_key,
            request_payload_hash=payload_hash,
            actor=req.actor,
        )
        try:
            response = self._llm.generate_structured(
                system_prompt=template.system_prompt,
                user_prompt=user_prompt,
                response_schema=GeneratedFactorHypothesisBatch,
                request_metadata=meta,
                max_tokens=template.max_response_tokens,
            )
            batch: GeneratedFactorHypothesisBatch = response.parsed  # type: ignore[assignment]
            if len(batch.candidates) > normalized.candidate_count:
                raise FactorLlmCandidateValidationError("CANDIDATE_COUNT_EXCEEDED", str(len(batch.candidates)))
            seen_names: set[str] = set()
            candidate_ids = []
            for seq, cand in enumerate(batch.candidates[: normalized.candidate_count], start=1):
                norm_name = normalize_candidate_name(cand.candidate_name)
                if norm_name in seen_names:
                    continue
                seen_names.add(norm_name)
                status = validate_hypothesis_candidate(cand)
                content_hash = canonical_hash(cand.model_dump(mode="json"))
                cid = self._candidates.create(
                    interaction_id=iid,
                    research_family_id=research_family_id,
                    candidate_type=CandidateType.HYPOTHESIS.value,
                    candidate_sequence=seq,
                    candidate_json=json_dumps({**cand.model_dump(mode="json"), "validation_status": status.value}),
                    candidate_content_hash=content_hash,
                    validation_status=status.value,
                    review_status=ReviewStatus.PENDING_REVIEW.value,
                )
                candidate_ids.append(cid)
            self._interactions.complete(
                iid,
                status="COMPLETED",
                model_id=response.model_id,
                structured_output_hash=canonical_hash(batch.model_dump(mode="json")),
                input_token_count=response.input_token_count,
                output_token_count=response.output_token_count,
                total_token_count=response.total_token_count,
                retry_count=response.retry_count,
                finish_reason=response.finish_reason,
            )
            return {"interaction_id": iid, "candidate_ids": candidate_ids, "status": "completed"}
        except Exception as exc:
            code = getattr(exc, "code", "HYPOTHESIS_GENERATION_FAILED")
            self._interactions.fail(iid, error_code=code, error_summary=str(exc)[:500])
            raise
