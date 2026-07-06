"""Repository CRUD and immutability tests for Factor Discovery."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.formatter import format_factor_expression
from models.schemas_factor_discovery import FactorDefinition, FactorDirection, FactorHypothesis, InputDataClass
from services.factor_discovery.errors import FactorDefinitionConflictError
from services.factor_discovery.repositories import (
    FactorDefinitionRepository,
    FactorHypothesisRepository,
    FactorResearchFamilyRepository,
)


def test_hypothesis_create_and_get(isolated_backend_env):
    repo = FactorHypothesisRepository()
    hyp = FactorHypothesis(
        hypothesis_id="hyp_test_1",
        name="Momentum",
        economic_rationale="Prices trend",
        expected_mechanism="Underreaction",
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="research",
        holding_period_sessions=21,
        rebalance_frequency="monthly",
        required_data_classes=[InputDataClass.PRICE],
    )
    repo.create(hyp, created_by="tester")
    row = repo.get("hyp_test_1")
    assert row is not None
    assert row.created_by == "tester"
    assert row.economic_rationale == "Prices trend"


def test_factor_version_idempotent_same_content(isolated_backend_env):
    ast = parse_factor_expression("rank(return_126d)")
    definition = FactorDefinition(
        factor_id="repo_factor",
        version="1.0.0",
        display_name="Repo",
        expression=ast,
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="research",
        rebalance_frequency="monthly",
        holding_period_sessions=21,
    )
    repo = FactorDefinitionRepository()
    dsl = format_factor_expression(ast)
    repo.create_version(definition, created_by="a", canonical_dsl=dsl, canonical_ast=definition.expression.model_dump(mode="json"))
    repo.create_version(definition, created_by="b", canonical_dsl=dsl, canonical_ast=definition.expression.model_dump(mode="json"))
    row = repo.get("repo_factor", "1.0.0")
    assert row.created_by == "a"


def test_factor_version_conflict_different_content(isolated_backend_env):
    ast = parse_factor_expression("rank(return_126d)")
    definition = FactorDefinition(
        factor_id="repo_conflict",
        version="1.0.0",
        display_name="Repo",
        expression=ast,
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="research",
        rebalance_frequency="monthly",
        holding_period_sessions=21,
    )
    repo = FactorDefinitionRepository()
    dsl = format_factor_expression(ast)
    repo.create_version(definition, created_by="test", canonical_dsl=dsl, canonical_ast=definition.expression.model_dump(mode="json"))
    with pytest.raises(FactorDefinitionConflictError) as exc:
        repo.create_version(
            FactorDefinition(
                factor_id="repo_conflict",
                version="1.0.0",
                display_name="Other",
                expression=parse_factor_expression("rank(return_1d)"),
                expected_direction=FactorDirection.HIGHER_IS_BETTER,
                intended_universe="research",
                rebalance_frequency="monthly",
                holding_period_sessions=21,
            ),
            created_by="test",
            canonical_dsl="rank(return_1d)",
            canonical_ast={},
        )
    assert exc.value.code == "FACTOR_VERSION_CONFLICT"


def test_research_family_create_and_get(isolated_backend_env):
    family_id = FactorResearchFamilyRepository().create(
        research_objective="value",
        intended_universe="research",
        primary_horizon_sessions=21,
        data_source_policy_id="research_adjusted_daily_v1",
        validation_config_family_id="default_v1",
        created_by="test",
    )
    row = FactorResearchFamilyRepository().get(family_id)
    assert row is not None
    assert row.attempt_count_policy_version == "distinct_formula_evaluations_v1"
    assert row.closed is False
