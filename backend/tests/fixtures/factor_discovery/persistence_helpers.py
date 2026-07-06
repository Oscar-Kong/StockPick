"""Shared helpers for Factor Discovery persistence tests."""
from __future__ import annotations

import config
from engines.factor.discovery.formatter import format_factor_expression
from engines.factor.discovery.parser import parse_factor_expression
from models.schemas_factor_discovery import FactorDefinition, FactorDirection, FactorLifecycleStatus
from services.factor_discovery.repositories import FactorDefinitionRepository, FactorResearchFamilyRepository
from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_validation_context


def enable_factor_discovery(monkeypatch) -> None:
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_ENABLED", True, raising=False)


def seed_family_and_definition(
    *,
    factor_id: str = "test_factor",
    version: str = "1.0.0",
    dsl: str = "rank(return_126d)",
    status: FactorLifecycleStatus = FactorLifecycleStatus.COMPILED,
) -> tuple[str, FactorDefinition, dict]:
    ctx = build_validation_context()
    family_id = FactorResearchFamilyRepository().create(
        research_objective="test family",
        intended_universe="research",
        primary_horizon_sessions=ctx["validation_config"].primary_horizon_sessions,
        data_source_policy_id="research_adjusted_daily_v1",
        validation_config_family_id="default_v1",
        created_by="test",
    )
    ast = parse_factor_expression(dsl)
    definition = FactorDefinition(
        factor_id=factor_id,
        version=version,
        display_name=f"Test {factor_id}",
        expression=ast,
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="research",
        rebalance_frequency="monthly",
        holding_period_sessions=21,
        lifecycle_status=status,
    )
    FactorDefinitionRepository().create_version(
        definition,
        created_by="test",
        canonical_dsl=format_factor_expression(ast),
        canonical_ast=definition.expression.model_dump(mode="json"),
    )
    return family_id, definition, ctx
