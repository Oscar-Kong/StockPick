"""Typed errors for Factor Discovery LLM operations."""
from __future__ import annotations

from services.factor_discovery.errors import FactorDiscoveryError


class FactorLlmError(FactorDiscoveryError):
    pass


class FactorLlmDisabledError(FactorLlmError):
    pass


class FactorLlmProviderConfigurationError(FactorLlmError):
    pass


class FactorLlmCapabilityError(FactorLlmError):
    pass


class FactorLlmTimeoutError(FactorLlmError):
    pass


class FactorLlmRateLimitError(FactorLlmError):
    pass


class FactorLlmBudgetExceededError(FactorLlmError):
    pass


class FactorLlmStructuredOutputError(FactorLlmError):
    pass


class FactorLlmSchemaValidationError(FactorLlmError):
    pass


class FactorLlmPromptVersionError(FactorLlmError):
    pass


class FactorLlmCandidateValidationError(FactorLlmError):
    pass


class FactorLlmEvidenceValidationError(FactorLlmError):
    pass


class FactorLlmReviewConflictError(FactorLlmError):
    pass


class FactorLlmIdempotencyConflictError(FactorLlmError):
    pass
