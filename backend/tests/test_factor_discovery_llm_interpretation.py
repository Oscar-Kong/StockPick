"""Evidence validation and run interpretation tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from engines.factor.discovery.formatter import format_factor_expression
from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.validation_models import AcceptanceGateResult, FactorValidationArtifact, SealedTestStatus
from engines.quant_db import init_quant_db
from models.schemas_factor_discovery import FactorDefinition, FactorDirection, FactorLifecycleStatus
from services.factor_discovery.experiment_runner import FactorDiscoveryExperimentRunner, FactorDiscoveryRunRequest
from services.factor_discovery.llm.errors import FactorLlmEvidenceValidationError
from services.factor_discovery.llm.evidence_validator import _flatten_artifact, validate_interpretation
from services.factor_discovery.llm.interpretation_service import FactorRunInterpretationService
from services.factor_discovery.llm.models import EvidenceReference, FactorRunInterpretation, InterpretationRecommendation
from services.factor_discovery.repositories import FactorDefinitionRepository, FactorResearchFamilyRepository
from tests.fixtures.factor_discovery.llm.helpers import enable_llm_fixture, register_interpretation_fixture
from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_validation_context


@pytest.fixture
def llm_env(isolated_backend_env, monkeypatch):
    init_quant_db()
    config.FACTOR_DISCOVERY_ENABLED.set(True)
    return enable_llm_fixture(monkeypatch)


def test_fabricated_metric_rejected():
    artifact = FactorValidationArtifact(
        formula_hash="sha256:x",
        plan_hash="sha256:y",
        panel_hash="sha256:z",
        execution_hash="sha256:e",
        validation_config_hash="sha256:c",
        period_resolution_hash="sha256:p",
        validation_artifact_hash="sha256:v",
        factor_direction="HIGHER_IS_BETTER",
        primary_horizon_sessions=21,
        validation_metrics={"rank_ic_mean": "0.05"},
        acceptance_gate=AcceptanceGateResult(overall_status="INCONCLUSIVE"),
        sealed_test=SealedTestStatus(status="SEALED", session_count=63, opened=False),
    )
    interpretation = FactorRunInterpretation(
        plain_language_summary="Looks good.",
        factor_intent="x",
        discovery_assessment="x",
        validation_assessment="x",
        walk_forward_assessment="x",
        cost_turnover_assessment="x",
        robustness_assessment="x",
        significance_assessment="x",
        recommended_next_action=InterpretationRecommendation.KEEP_RESEARCHING,
        evidence_references=[
            EvidenceReference(path="validation.rank_ic_mean", value="0.99", claim="ic")
        ],
    )
    with pytest.raises(FactorLlmEvidenceValidationError) as exc:
        validate_interpretation(interpretation, artifact)
    assert exc.value.code == "EVIDENCE_VALUE_MISMATCH"


def test_closed_artifact_no_sealed_metric_paths():
    artifact = FactorValidationArtifact(
        formula_hash="sha256:x",
        plan_hash="sha256:y",
        panel_hash="sha256:z",
        execution_hash="sha256:e",
        validation_config_hash="sha256:c",
        period_resolution_hash="sha256:p",
        validation_artifact_hash="sha256:v",
        factor_direction="HIGHER_IS_BETTER",
        primary_horizon_sessions=21,
        sealed_test=SealedTestStatus(status="SEALED", session_count=63, opened=False),
        acceptance_gate=AcceptanceGateResult(overall_status="FAIL"),
    )
    flat = _flatten_artifact(artifact)
    assert not any("sealed_ic" in k for k in flat)


def test_closed_run_interpretation_e2e(llm_env):
    ctx = build_validation_context()
    family_id = FactorResearchFamilyRepository().create(
        research_objective="interp",
        intended_universe="research",
        primary_horizon_sessions=ctx["validation_config"].primary_horizon_sessions,
        data_source_policy_id="research_adjusted_daily_v1",
        validation_config_family_id="default_v1",
        created_by="test",
    )
    ast = parse_factor_expression("rank(return_126d)")
    definition = FactorDefinition(
        factor_id="interp_mom",
        version="1.0.0",
        display_name="Interp",
        expression=ast,
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="research",
        rebalance_frequency="monthly",
        holding_period_sessions=21,
        lifecycle_status=FactorLifecycleStatus.COMPILED,
    )
    FactorDefinitionRepository().create_version(
        definition,
        created_by="test",
        canonical_dsl=format_factor_expression(ast),
        canonical_ast=definition.expression.model_dump(mode="json"),
    )
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
    assert run["status"] == "completed"
    from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
    from services.factor_discovery.repositories import FactorValidationArtifactRepository

    row = FactorValidationArtifactRepository().get(run["artifact_id"])
    artifact = load_and_verify_artifact_record(row)
    flat = _flatten_artifact(artifact)
    refs = []
    if "validation.rank_ic_mean" in flat:
        refs.append(
            EvidenceReference(
                path="validation.rank_ic_mean",
                value=flat["validation.rank_ic_mean"],
                claim="validation IC",
            )
        )
    register_interpretation_fixture(evidence=refs)
    out = FactorRunInterpretationService(llm_client=llm_env).interpret(run["run_id"], actor="tester")
    assert out["interpretation_candidate_id"]
