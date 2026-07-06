"""Deterministic post-LLM validation for hypothesis candidates."""
from __future__ import annotations

import re

from models.schemas_factor_discovery import InputDataClass
from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities
from services.factor_discovery.llm.field_catalog import forbidden_outcome_fields
from services.factor_discovery.llm.models import (
    CandidateValidationStatus,
    GeneratedFactorHypothesisCandidate,
)

_CERTAINTY_RE = re.compile(r"\b(guaranteed|proven profitable|validated factor|production ready)\b", re.I)


def validate_hypothesis_candidate(candidate: GeneratedFactorHypothesisCandidate) -> CandidateValidationStatus:
    if not candidate.economic_rationale.strip():
        return CandidateValidationStatus.INVALID
    if _CERTAINTY_RE.search(candidate.economic_rationale):
        return CandidateValidationStatus.INVALID
    forbidden = forbidden_outcome_fields()
    for field in candidate.proposed_fields:
        if field in forbidden:
            return CandidateValidationStatus.INVALID
    caps = assess_historical_store_capabilities()
    unsupported = [f for f in candidate.proposed_fields if f not in caps.supported_fields and f not in {"sector", "industry", "market_cap", "free_cash_flow"}]
    if unsupported and not caps.price_research_available:
        return CandidateValidationStatus.UNSUPPORTED_DATA
    if unsupported:
        return CandidateValidationStatus.PARTIALLY_SUPPORTED
    try:
        for dc in candidate.required_data_classes:
            InputDataClass(dc)
    except ValueError:
        return CandidateValidationStatus.INVALID
    return CandidateValidationStatus.EXECUTABLE


def normalize_candidate_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())
