"""Promising candidate policy tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.experiment_runner import FactorDiscoveryExperimentRunner, FactorDiscoveryRunRequest
from services.factor_discovery.mining.promising_policy import evaluate_promising
from tests.fixtures.factor_discovery.persistence_helpers import enable_factor_discovery, seed_family_and_definition


def test_promising_requires_multiple_rules(isolated_backend_env, monkeypatch):
    enable_factor_discovery(monkeypatch)
    family_id, definition, ctx = seed_family_and_definition()
    runner = FactorDiscoveryExperimentRunner(fixture_builder=lambda: ctx["panel"])
    run = runner.run(
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
    from services.factor_discovery.repositories import FactorValidationArtifactRepository
    from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record

    art_row = FactorValidationArtifactRepository().get(run["artifact_id"])
    artifact = load_and_verify_artifact_record(art_row)
    result = evaluate_promising(artifact, integrity_ok=True)
    assert result.overall in {"PROMISING_FOR_HUMAN_REVIEW", "NOT_PROMISING", "INCONCLUSIVE"}
    assert len(result.rules) >= 3
