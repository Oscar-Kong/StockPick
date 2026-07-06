"""Multiple-testing staleness and explicit revalidation."""
from __future__ import annotations

from dataclasses import dataclass

from engines.factor.discovery.validation_hashing import validation_config_hash
from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit, FactorDirection, FactorLifecycleStatus
from services.factor_discovery.experiment_runner import FactorDiscoveryExperimentRunner, FactorDiscoveryRunRequest
from services.factor_discovery.multiple_testing_service import derive_family_size, is_correction_stale
from services.factor_discovery.repositories import (
    FactorAttemptLedgerRepository,
    FactorDefinitionRepository,
    FactorDiscoveryRunRepository,
    FactorResearchFamilyRepository,
    FactorValidationArtifactRepository,
)
from services.research_json import json_loads


@dataclass(frozen=True)
class StalenessReport:
    artifact_id: str
    family_size_at_evaluation: int | None
    current_family_size: int
    stale: bool
    count_policy_version: str


def evaluate_staleness(artifact_id: str) -> StalenessReport:
    repo = FactorValidationArtifactRepository()
    row = repo.get(artifact_id)
    if row is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    run = FactorDiscoveryRunRepository().get(row.run_id)
    if run is None:
        raise ValueError("run not found")
    attempts = FactorAttemptLedgerRepository().list_for_family(run.research_family_id)
    family = FactorResearchFamilyRepository().get(run.research_family_id)
    vconfig = FactorValidationConfig.model_validate(json_loads(run.validation_config_json, {}))
    current = derive_family_size(
        attempts,
        primary_horizon_sessions=vconfig.primary_horizon_sessions,
        validation_config_family_id=family.validation_config_family_id if family else "default_v1",
    )
    stale = is_correction_stale(
        family_size_at_evaluation=row.family_size_at_evaluation or 0,
        current_derived_size=current.derived_family_size,
    )
    return StalenessReport(
        artifact_id=artifact_id,
        family_size_at_evaluation=row.family_size_at_evaluation,
        current_family_size=current.effective_family_size,
        stale=stale,
        count_policy_version=current.policy_version,
    )


def revalidate_factor(
    *,
    prior_artifact_id: str,
    created_by: str,
    fixture_builder=None,
) -> dict:
    """Create new attempt + artifact using frozen formula/snapshot with current family size."""
    prior = FactorValidationArtifactRepository().get(prior_artifact_id)
    if prior is None:
        raise ValueError("prior artifact not found")
    run = FactorDiscoveryRunRepository().get(prior.run_id)
    if run is None:
        raise ValueError("prior run not found")
    runner = FactorDiscoveryExperimentRunner(fixture_builder=fixture_builder)
    result = runner.run(
        FactorDiscoveryRunRequest(
            experiment_id=run.experiment_id,
            job_id=None,
            factor_id=run.factor_id,
            factor_version=run.factor_version,
            research_family_id=run.research_family_id,
            period_split=DiscoveryPeriodSplit.model_validate(json_loads(run.period_split_json, {})),
            validation_config=FactorValidationConfig.model_validate(json_loads(run.validation_config_json, {})),
            created_by=created_by,
        )
    )
    if result.get("artifact_id"):
        FactorValidationArtifactRepository().link_revalidation(
            result["artifact_id"],
            revalidation_of_artifact_id=prior_artifact_id,
        )
    return result
