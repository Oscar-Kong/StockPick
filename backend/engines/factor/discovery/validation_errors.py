"""Typed errors for Factor Discovery validation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorValidationError(Exception):
    code: str
    message: str
    context: str | None = None

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        if self.context:
            base = f"{base} ({self.context})"
        return base


class ValidationConfigError(FactorValidationError):
    pass


class OutcomeGenerationError(FactorValidationError):
    pass


class PeriodResolutionError(FactorValidationError):
    pass


class HashMismatchError(FactorValidationError):
    pass


class SealedTestAccessError(FactorValidationError):
    pass


class InsufficientDataError(FactorValidationError):
    pass
