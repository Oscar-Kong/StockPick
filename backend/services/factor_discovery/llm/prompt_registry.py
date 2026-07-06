"""Versioned prompt-template registry for Factor Discovery LLM."""
from __future__ import annotations

from dataclasses import dataclass

from services.factor_discovery.llm.models import LlmOperationType

_SAFETY_RULES = """
You are a factor research assistant for quantitative equity research.
RULES (mandatory):
- Do NOT execute Python, SQL, or any code.
- Do NOT invent backtest results, IC values, Sharpe ratios, or p-values.
- Do NOT request or reveal sealed-test performance metrics.
- Do NOT approve lifecycle transitions (VALIDATED, PAPER, PRODUCTION).
- Do NOT use outcome/forward-return fields as factor inputs.
- Use ONLY fields from the provided available-field catalog.
- Deterministic parsing, compilation, execution, and validation services are authoritative.
- All profitability claims are unproven until human-reviewed experiments complete.
- Return ONLY valid JSON matching the requested schema. No markdown fences.
"""


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    version: str
    operation_type: LlmOperationType
    system_prompt: str
    input_schema_version: str
    output_schema_version: str
    max_candidates: int
    max_response_tokens: int


TEMPLATES: dict[str, PromptTemplate] = {
    "factor_research_request_normalizer_v1": PromptTemplate(
        template_id="factor_research_request_normalizer_v1",
        version="1.0.0",
        operation_type=LlmOperationType.REQUEST_NORMALIZE,
        system_prompt=_SAFETY_RULES
        + "\nNormalize the research request into clear, bounded objectives. Do not expand universe or data scope.",
        input_schema_version="factor-llm-v1",
        output_schema_version="factor-llm-v1",
        max_candidates=1,
        max_response_tokens=400,
    ),
    "factor_hypothesis_generator_v1": PromptTemplate(
        template_id="factor_hypothesis_generator_v1",
        version="1.0.0",
        operation_type=LlmOperationType.HYPOTHESIS_GENERATE,
        system_prompt=_SAFETY_RULES
        + "\nGenerate economic factor hypotheses. Each must state profitability is unproven. Use only available fields.",
        input_schema_version="factor-llm-v1",
        output_schema_version="factor-llm-v1",
        max_candidates=5,
        max_response_tokens=1200,
    ),
    "factor_hypothesis_critic_v1": PromptTemplate(
        template_id="factor_hypothesis_critic_v1",
        version="1.0.0",
        operation_type=LlmOperationType.HYPOTHESIS_CRITIQUE,
        system_prompt=_SAFETY_RULES
        + "\nCritique one hypothesis candidate. Do not claim numerical performance. Do not see sealed results.",
        input_schema_version="factor-llm-v1",
        output_schema_version="factor-llm-v1",
        max_candidates=1,
        max_response_tokens=800,
    ),
    "factor_dsl_translator_v1": PromptTemplate(
        template_id="factor_dsl_translator_v1",
        version="1.0.0",
        operation_type=LlmOperationType.FORMULA_TRANSLATE,
        system_prompt=_SAFETY_RULES
        + "\nTranslate ONE approved hypothesis into Factor DSL v1 only. Prefer simple formulas. No Python/SQL.",
        input_schema_version="factor-llm-v1",
        output_schema_version="factor-llm-v1",
        max_candidates=3,
        max_response_tokens=600,
    ),
    "factor_formula_reviewer_v1": PromptTemplate(
        template_id="factor_formula_reviewer_v1",
        version="1.0.0",
        operation_type=LlmOperationType.FORMULA_REVIEW,
        system_prompt=_SAFETY_RULES
        + "\nReview a compiled formula for fidelity and risks. Do NOT alter the DSL or generate replacements.",
        input_schema_version="factor-llm-v1",
        output_schema_version="factor-llm-v1",
        max_candidates=1,
        max_response_tokens=700,
    ),
    "factor_run_interpreter_v1": PromptTemplate(
        template_id="factor_run_interpreter_v1",
        version="1.0.0",
        operation_type=LlmOperationType.RUN_INTERPRET,
        system_prompt=_SAFETY_RULES
        + "\nInterpret persisted factor validation results. Quote ONLY metrics provided. Include evidence_references.",
        input_schema_version="factor-llm-v1",
        output_schema_version="factor-llm-v1",
        max_candidates=1,
        max_response_tokens=1200,
    ),
}


def get_template(template_id: str) -> PromptTemplate:
    if template_id not in TEMPLATES:
        from services.factor_discovery.llm.errors import FactorLlmPromptVersionError

        raise FactorLlmPromptVersionError("UNKNOWN_PROMPT_TEMPLATE", template_id)
    return TEMPLATES[template_id]
