"""Typed errors for Factor Discovery panel execution."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorExecutionError(Exception):
    code: str
    message: str
    context: str | None = None

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        if self.context:
            base = f"{base} ({self.context})"
        return base


class InvalidInputPanelError(FactorExecutionError):
    pass


class PanelPolicyMismatchError(FactorExecutionError):
    pass


class PanelLimitError(FactorExecutionError):
    pass


class MissingFieldDataError(FactorExecutionError):
    pass


class PointInTimeViolationError(FactorExecutionError):
    pass


class AdjustedPriceViolationError(FactorExecutionError):
    pass


class UniverseEvidenceError(FactorExecutionError):
    pass


class OperatorExecutionError(FactorExecutionError):
    pass


class NeutralizationError(FactorExecutionError):
    pass


class DerivedFieldError(FactorExecutionError):
    pass


class ExecutionDeterminismError(FactorExecutionError):
    pass
