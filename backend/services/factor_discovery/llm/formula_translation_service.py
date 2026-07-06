"""DSL translation with deterministic parser/compiler verification."""
from __future__ import annotations

import json
import re

from config import FACTOR_DISCOVERY_LLM_MAX_FORMULAS
from engines.factor.discovery.compiler import compile_factor_definition
from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
from engines.factor.discovery.formatter import format_factor_expression
from engines.factor.discovery.parser import parse_factor_expression
from models.schemas_factor_discovery import FactorDefinition, FactorDirection, FactorLifecycleStatus
from services.factor_discovery.llm.budgets import enforce_candidate_limit
from services.factor_discovery.llm.capabilities import require_llm_operation
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.client import get_factor_discovery_llm_client
from services.factor_discovery.llm.errors import FactorLlmReviewConflictError
from services.factor_discovery.llm.field_catalog import available_fields_for_llm, forbidden_outcome_fields
from services.factor_discovery.llm.hashing import canonical_hash, text_hash
from services.factor_discovery.llm.interaction_repository import FactorLlmInteractionRepository
from services.factor_discovery.llm.models import (
    CandidateType,
    FactorLlmRequestMetadata,
    FormulaCompileStatus,
    GeneratedFactorFormula,
    LlmOperationType,
    ReviewStatus,
)
from services.factor_discovery.llm.prompt_registry import get_template
from services.research_json import json_dumps, json_loads


def _clean_dsl_source(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:\w+)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


class FactorFormulaTranslationService:
    def __init__(self, *, llm_client=None) -> None:
        self._llm = llm_client or get_factor_discovery_llm_client()
        self._interactions = FactorLlmInteractionRepository()
        self._candidates = FactorLlmCandidateRepository()

    def translate(self, hypothesis_candidate_id: str, *, actor: str = "api", max_formulas: int = 1) -> dict:
        require_llm_operation(LlmOperationType.FORMULA_TRANSLATE)
        hyp = self._candidates.get(hypothesis_candidate_id)
        if hyp is None or hyp.candidate_type != CandidateType.HYPOTHESIS.value:
            raise ValueError("hypothesis candidate not found")
        if hyp.review_status != ReviewStatus.APPROVED.value:
            raise FactorLlmReviewConflictError("HYPOTHESIS_NOT_APPROVED", hyp.review_status)
        enforce_candidate_limit(min(max_formulas, FACTOR_DISCOVERY_LLM_MAX_FORMULAS), operation="formula")

        template = get_template("factor_dsl_translator_v1")
        hyp_data = json_loads(hyp.candidate_json, {})
        user_prompt = json.dumps(
            {
                "approved_hypothesis": hyp_data,
                "available_fields": available_fields_for_llm(),
                "forbidden_fields": sorted(forbidden_outcome_fields()),
                "supported_operators": ["rank", "zscore", "lag", "rolling_mean", "neutralize"],
            },
            indent=2,
        )
        meta = FactorLlmRequestMetadata(
            operation_type=LlmOperationType.FORMULA_TRANSLATE,
            actor=actor,
            research_family_id=hyp.research_family_id,
        )
        iid = self._interactions.create(
            operation_type=LlmOperationType.FORMULA_TRANSLATE.value,
            research_family_id=hyp.research_family_id,
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
                response_schema=GeneratedFactorFormula,
                request_metadata=meta,
            )
            formula: GeneratedFactorFormula = response.parsed  # type: ignore[assignment]
            formula = formula.model_copy(update={"hypothesis_candidate_id": hypothesis_candidate_id})
            dsl = _clean_dsl_source(formula.dsl_source)
            compile_status, compile_meta = self._verify_formula(dsl, formula.expected_direction)
            content = {
                **formula.model_dump(mode="json"),
                "original_dsl": formula.dsl_source,
                "canonical_dsl": compile_meta.get("canonical_dsl"),
                "compile_status": compile_status.value,
                "compile_meta": compile_meta,
            }
            content_hash = canonical_hash(content)
            cid = self._candidates.create(
                interaction_id=iid,
                research_family_id=hyp.research_family_id,
                hypothesis_candidate_id=hypothesis_candidate_id,
                candidate_type=CandidateType.FORMULA.value,
                candidate_sequence=1,
                candidate_json=json_dumps(content),
                candidate_content_hash=content_hash,
                validation_status=compile_status.value,
                formula_hash=compile_meta.get("formula_hash"),
                review_status=ReviewStatus.PENDING_REVIEW.value,
            )
            self._interactions.complete(iid, status="COMPLETED", model_id=response.model_id, structured_output_hash=content_hash)
            return {"interaction_id": iid, "formula_candidate_id": cid, "compile_status": compile_status.value}
        except Exception as exc:
            code = getattr(exc, "code", "FORMULA_TRANSLATION_FAILED")
            self._interactions.fail(iid, error_code=code, error_summary=str(exc)[:500])
            raise

    def _verify_formula(self, dsl: str, direction: FactorDirection) -> tuple[FormulaCompileStatus, dict]:
        meta: dict = {"original_dsl": dsl}
        if any(x in dsl.lower() for x in ("import ", "select ", "eval(", "__import__")):
            meta["error"] = "code injection detected"
            return FormulaCompileStatus.PARSE_FAILED, meta
        try:
            ast = parse_factor_expression(dsl)
        except Exception as exc:
            meta["error"] = str(exc)[:200]
            return FormulaCompileStatus.PARSE_FAILED, meta
        canonical_dsl = format_factor_expression(ast)
        meta["canonical_dsl"] = canonical_dsl
        try:
            definition = FactorDefinition(
                factor_id="llm_candidate",
                version="0.0.0",
                display_name="LLM Candidate",
                expression=ast,
                expected_direction=direction,
                intended_universe="research",
                rebalance_frequency="monthly",
                holding_period_sessions=21,
                lifecycle_status=FactorLifecycleStatus.DRAFT,
            )
            plan = compile_factor_definition(
                definition,
                field_registry=build_default_field_registry(),
                data_source_policy=default_data_source_policy(),
            )
            meta["formula_hash"] = plan.formula_hash_value
            meta["plan_hash"] = plan.plan_hash_value
            meta["required_fields"] = sorted(plan.required_field_ids)
            meta["compiler_version"] = plan.compiler_version
            return FormulaCompileStatus.COMPILED_FOR_REVIEW, meta
        except Exception as exc:
            meta["error"] = str(exc)[:200]
            return FormulaCompileStatus.COMPILE_FAILED, meta
