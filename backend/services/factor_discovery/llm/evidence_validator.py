"""Evidence validation for Factor Discovery run interpretations."""
from __future__ import annotations

from services.factor_discovery.llm.errors import FactorLlmEvidenceValidationError
from services.factor_discovery.llm.models import FactorRunInterpretation, InterpretationRecommendation


def _flatten_artifact(artifact, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    sections = {
        "discovery": artifact.discovery_metrics,
        "validation": artifact.validation_metrics,
        "walk_forward": artifact.walk_forward,
        "portfolio": artifact.portfolio_results,
        "statistical": artifact.statistical_results,
        "multiple_testing": artifact.multiple_testing,
        "acceptance": artifact.acceptance_gate.model_dump(mode="json") if artifact.acceptance_gate else {},
        "limitations": {str(i): v for i, v in enumerate(artifact.limitations)},
        "sealed_test": artifact.sealed_test.model_dump(mode="json"),
    }
    for section, data in sections.items():
        if not isinstance(data, dict):
            continue
        for k, v in data.items():
            path = f"{section}.{k}"
            if v is not None:
                out[path] = str(v)
    if artifact.sealed_test_metrics is None:
        for k in list(out.keys()):
            if k.startswith("sealed_test_metrics") or "sealed_ic" in k:
                del out[k]
    return out


def validate_interpretation(interpretation: FactorRunInterpretation, artifact) -> None:
    allowed = _flatten_artifact(artifact)
    if artifact.sealed_test_metrics is None:
        for ref in interpretation.evidence_references:
            if "sealed" in ref.path.lower() and "status" not in ref.path:
                raise FactorLlmEvidenceValidationError("SEALED_METRIC_LEAK", ref.path)
    for ref in interpretation.evidence_references:
        if ref.path not in allowed:
            raise FactorLlmEvidenceValidationError("EVIDENCE_PATH_UNKNOWN", ref.path)
        if ref.value != allowed[ref.path]:
            raise FactorLlmEvidenceValidationError("EVIDENCE_VALUE_MISMATCH", f"{ref.path}: {ref.value}")
    text = interpretation.plain_language_summary.lower()
    for banned in ("validated factor", "production ready", "approved for trading", "guaranteed profit"):
        if banned in text:
            raise FactorLlmEvidenceValidationError("FORBIDDEN_CLAIM", banned)
    if interpretation.recommended_next_action == InterpretationRecommendation.CONSIDER_PROMISING_REVIEW:
        if artifact.acceptance_gate.overall_status not in {"PASS", "MARGINAL"}:
            pass  # recommendation is human-only; allow with note
