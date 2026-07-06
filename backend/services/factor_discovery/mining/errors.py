"""Typed errors for Factor Discovery mining sessions."""
from __future__ import annotations

from services.factor_discovery.errors import FactorDiscoveryError


class FactorMiningError(FactorDiscoveryError):
    pass


class MiningFeatureDisabledError(FactorMiningError):
    pass


class MiningSessionNotFoundError(FactorMiningError):
    pass


class MiningSessionStateError(FactorMiningError):
    pass


class MiningSessionAuthorizationError(FactorMiningError):
    pass


class MiningBudgetExceededError(FactorMiningError):
    pass


class MiningValidationExposureExceededError(FactorMiningError):
    pass


class MiningPauseRequiredError(FactorMiningError):
    pass


class MiningDuplicateFormulaError(FactorMiningError):
    pass


class MiningRevisionPolicyError(FactorMiningError):
    pass


class MiningStoppingConditionReached(FactorMiningError):
    pass


class MiningConcurrencyConflictError(FactorMiningError):
    pass


class MiningIntegrityError(FactorMiningError):
    pass


class MiningProviderCapabilityError(FactorMiningError):
    pass


class MiningExperimentLaunchError(FactorMiningError):
    pass


class MiningRecoveryError(FactorMiningError):
    pass


class MiningCancellationError(FactorMiningError):
    pass
