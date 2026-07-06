"""Typed errors for Factor Discovery persistence and runner."""
from __future__ import annotations


class FactorDiscoveryError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ArtifactIntegrityError(FactorDiscoveryError):
    pass


class SealedTestReservationError(FactorDiscoveryError):
    pass


class FactorLifecycleError(FactorDiscoveryError):
    pass


class IdempotencyConflictError(FactorDiscoveryError):
    pass


class ProductionPromotionError(FactorLifecycleError):
    pass


class FactorDefinitionConflictError(FactorDiscoveryError):
    pass
