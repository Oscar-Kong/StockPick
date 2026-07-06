"""Persistence model and migration tests for Factor Discovery Phase 5."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.db_engine import get_engine
from data.cache import init_db


@pytest.fixture
def db():
    init_db()
    return get_engine()


def test_factor_discovery_tables_exist(db):
    tables = set(inspect(db).get_table_names())
    expected = {
        "factor_hypothesis_records",
        "factor_research_families",
        "factor_definition_records",
        "factor_research_data_snapshots",
        "factor_discovery_runs",
        "factor_discovery_attempts",
        "factor_validation_artifact_records",
        "factor_sealed_test_receipts",
        "factor_status_events",
    }
    assert expected.issubset(tables)


def test_factor_definition_unique_constraint(db):
    from engines.factor.discovery.parser import parse_factor_expression
    from engines.factor.discovery.formatter import format_factor_expression
    from models.schemas_factor_discovery import FactorDefinition, FactorDirection
    from services.factor_discovery.repositories import FactorDefinitionRepository
    from services.factor_discovery.errors import FactorDefinitionConflictError

    ast = parse_factor_expression("rank(return_126d)")
    definition = FactorDefinition(
        factor_id="test_factor_a",
        version="1.0.0",
        display_name="Test",
        expression=ast,
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="research",
        rebalance_frequency="monthly",
        holding_period_sessions=21,
    )
    repo = FactorDefinitionRepository()
    dsl = format_factor_expression(ast)
    repo.create_version(definition, created_by="test", canonical_dsl=dsl, canonical_ast=definition.expression.model_dump(mode="json"))
    with pytest.raises(FactorDefinitionConflictError):
        repo.create_version(
            FactorDefinition(
                factor_id="test_factor_a",
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
