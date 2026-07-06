"""Run interpretation via schema-constrained LLM."""
from __future__ import annotations

import json

from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
from services.factor_discovery.llm.capabilities import require_llm_operation
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.client import get_factor_discovery_llm_client
from services.factor_discovery.llm.errors import FactorLlmEvidenceValidationError
from services.factor_discovery.llm.evidence_validator import validate_interpretation
from services.factor_discovery.llm.hashing import canonical_hash, text_hash
from services.factor_discovery.llm.interaction_repository import FactorLlmInteractionRepository
from services.factor_discovery.llm.models import (
    CandidateType,
    FactorLlmRequestMetadata,
    FactorRunInterpretation,
    LlmOperationType,
    ReviewStatus,
)
from services.factor_discovery.llm.prompt_registry import get_template
from services.factor_discovery.repositories import FactorDiscoveryRunRepository, FactorValidationArtifactRepository
from services.research_json import json_dumps


def _artifact_context_for_llm(artifact) -> dict:
    ctx = {
        "discovery_metrics": artifact.discovery_metrics,
        "validation_metrics": artifact.validation_metrics,
        "walk_forward": artifact.walk_forward,
        "portfolio_results": artifact.portfolio_results,
        "statistical_results": artifact.statistical_results,
        "multiple_testing": artifact.multiple_testing,
        "acceptance_gate": artifact.acceptance_gate.model_dump(mode="json"),
        "limitations": artifact.limitations,
        "warnings": artifact.warnings,
        "sealed_test": artifact.sealed_test.model_dump(mode="json"),
    }
    if artifact.sealed_test_metrics is not None:
        ctx["sealed_test_metrics"] = artifact.sealed_test_metrics
    return ctx


class FactorRunInterpretationService:
    def __init__(self, *, llm_client=None) -> None:
        self._llm = llm_client or get_factor_discovery_llm_client()
        self._interactions = FactorLlmInteractionRepository()
        self._candidates = FactorLlmCandidateRepository()
        self._runs = FactorDiscoveryRunRepository()

    def interpret(self, run_id: str, *, actor: str = "api", include_opened_sealed: bool = False) -> dict:
        require_llm_operation(LlmOperationType.RUN_INTERPRET)
        run = self._runs.get(run_id)
        if run is None or run.status != "completed" or not run.closed_artifact_hash:
            raise ValueError("completed run with closed artifact required")
        artifact_row = FactorValidationArtifactRepository().get_by_hash(run.closed_artifact_hash)
        if artifact_row is None:
            raise ValueError("artifact not found")
        artifact = load_and_verify_artifact_record(artifact_row)
        if artifact.sealed_test_metrics and not include_opened_sealed:
            artifact = artifact.model_copy(update={"sealed_test_metrics": None})

        template = get_template("factor_run_interpreter_v1")
        ctx = _artifact_context_for_llm(artifact)
        user_prompt = json.dumps({"run_id": run_id, "artifact_evidence": ctx}, indent=2)
        meta = FactorLlmRequestMetadata(
            operation_type=LlmOperationType.RUN_INTERPRET,
            actor=actor,
            run_id=run_id,
            research_family_id=run.research_family_id,
        )
        iid = self._interactions.create(
            operation_type=LlmOperationType.RUN_INTERPRET.value,
            run_id=run_id,
            research_family_id=run.research_family_id,
            provider_id=getattr(self._llm, "provider_id", "unknown"),
            model_id="pending",
            prompt_template_id=template.template_id,
            prompt_template_version=template.version,
            system_prompt_hash=text_hash(template.system_prompt),
            user_prompt_hash=text_hash(user_prompt),
            structured_input_hash=run.closed_artifact_hash,
            response_schema_version="factor-llm-v1",
            status="RUNNING",
            actor=actor,
        )
        try:
            response = self._llm.generate_structured(
                system_prompt=template.system_prompt,
                user_prompt=user_prompt,
                response_schema=FactorRunInterpretation,
                request_metadata=meta,
                max_tokens=template.max_response_tokens,
            )
            interpretation: FactorRunInterpretation = response.parsed  # type: ignore[assignment]
            validate_interpretation(interpretation, artifact)
            content_hash = canonical_hash(interpretation.model_dump(mode="json"))
            cid = self._candidates.create(
                interaction_id=iid,
                research_family_id=run.research_family_id,
                candidate_type=CandidateType.INTERPRETATION.value,
                candidate_sequence=1,
                candidate_json=json_dumps(interpretation.model_dump(mode="json")),
                candidate_content_hash=content_hash,
                review_status=ReviewStatus.PENDING_REVIEW.value,
            )
            self._interactions.complete(iid, status="COMPLETED", model_id=response.model_id, structured_output_hash=content_hash)
            return {"interaction_id": iid, "interpretation_candidate_id": cid}
        except FactorLlmEvidenceValidationError as exc:
            self._interactions.fail(iid, error_code=exc.code, error_summary=str(exc)[:500])
            raise
        except Exception as exc:
            code = getattr(exc, "code", "INTERPRETATION_FAILED")
            self._interactions.fail(iid, error_code=code, error_summary=str(exc)[:500])
            raise
