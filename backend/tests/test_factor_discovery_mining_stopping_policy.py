"""Post-validation decision engine tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.experiment_runner import FactorDiscoveryExperimentRunner, FactorDiscoveryRunRequest
from services.factor_discovery.mining.models import FactorMiningBudgetPolicy, PostValidationAction
from services.factor_discovery.mining.post_validation_decision import decide_post_validation
from tests.fixtures.factor_discovery.persistence_helpers import enable_factor_discovery, seed_family_and_definition


def test_decision_engine_returns_typed_action(isolated_backend_env, monkeypatch):
    enable_factor_discovery(monkeypatch)
    family_id, definition, ctx = seed_family_and_definition()
    run = FactorDiscoveryExperimentRunner(fixture_builder=lambda: ctx["panel"]).run(
        FactorDiscoveryRunRequest(
            experiment_id=None,
            job_id=None,
            factor_id=definition.factor_id,
            factor_version=definition.version,
            research_family_id=family_id,
            period_split=ctx["period_split"],
            validation_config=ctx["validation_config"],
            created_by="test",
        )
    )
    from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
    from services.factor_discovery.repositories import FactorValidationArtifactRepository

    artifact = load_and_verify_artifact_record(FactorValidationArtifactRepository().get(run["artifact_id"]))
    decision = decide_post_validation(
        lineage_id="lin1",
        evaluation_id="eval1",
        artifact=artifact,
        artifact_integrity_ok=True,
        revision_depth=0,
        budget=FactorMiningBudgetPolicy(max_revision_rounds_per_lineage=2),
        usage_formulas_evaluated=1,
        exposure_available=True,
    )
    assert decision.recommended_action in PostValidationAction
