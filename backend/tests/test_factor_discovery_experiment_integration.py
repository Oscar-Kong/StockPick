"""End-to-end Factor Discovery experiment integration tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.formatter import format_factor_expression
from models.schemas_factor_discovery import FactorDefinition, FactorDirection, FactorLifecycleStatus
from services.factor_discovery.experiment_runner import FactorDiscoveryExperimentRunner, FactorDiscoveryRunRequest
from services.factor_discovery.repositories import (
    FactorDefinitionRepository,
    FactorResearchFamilyRepository,
)
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel
from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_validation_context


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_ENABLED", True, raising=False)


def test_e2e_predictive_factor_closed_test(enabled, isolated_backend_env):
    ctx = build_validation_context()
    family_id = FactorResearchFamilyRepository().create(
        research_objective="momentum test",
        intended_universe="research",
        primary_horizon_sessions=ctx["validation_config"].primary_horizon_sessions,
        data_source_policy_id="research_adjusted_daily_v1",
        validation_config_family_id="default_v1",
        created_by="test",
    )
    ast = parse_factor_expression("rank(return_126d)")
    definition = FactorDefinition(
        factor_id="e2e_momentum",
        version="1.0.0",
        display_name="E2E Momentum",
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
    result = runner.run(
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
    assert result["status"] == "completed"
    assert result["artifact_id"]
    assert result["recommended_status"] in {None, "PROMISING"}


def test_e2e_empty_pit_universe_rejected(enabled, isolated_backend_env):
    ctx = build_validation_context()
    family_id = FactorResearchFamilyRepository().create(
        research_objective="empty universe",
        intended_universe="research",
        primary_horizon_sessions=21,
        data_source_policy_id="research_adjusted_daily_v1",
        validation_config_family_id="default_v1",
        created_by="test",
    )
    ast = parse_factor_expression("rank(return_126d)")
    definition = FactorDefinition(
        factor_id="e2e_empty",
        version="1.0.0",
        display_name="Empty",
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

    panel = build_research_panel(n_days=80)
    empty_panel = type(panel)(
        frame=panel.frame,
        eligibility=panel.eligibility & False,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
        has_universe_membership=False,
    )

    from services.factor_discovery.data_provider import FixtureFactorResearchDataProvider

    runner = FactorDiscoveryExperimentRunner(
        provider=FixtureFactorResearchDataProvider(panel_builder=lambda: empty_panel, empty_universe=True)
    )
    from services.factor_discovery.errors import FactorDiscoveryError

    with pytest.raises(FactorDiscoveryError) as exc:
        runner.run(
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
    assert exc.value.code == "EMPTY_PIT_UNIVERSE"
