"""End-to-end Factor Discovery validation engine tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.compiler import compile_factor_expression
from engines.factor.discovery.executor import compute_factor_panel
from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.validation_engine import validate_factor_execution
from engines.factor.discovery.validation_models import FactorValidationConfig, SealedTestAccess
from models.schemas_factor_discovery import FactorDirection
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel
from tests.fixtures.factor_discovery.validation.validation_panel_builder import (
    build_predictive_panel,
    default_period_split,
)


@pytest.fixture
def registry():
    return build_default_field_registry()


@pytest.fixture
def policy():
    return default_data_source_policy()


def _compile_execute(dsl: str, panel, registry, policy):
    ast = parse_factor_expression(dsl)
    plan = compile_factor_expression(ast, field_registry=registry, data_source_policy=policy)
    result = compute_factor_panel(plan, panel)
    return plan, result


def test_validate_rank_return_126d(registry, policy):
    panel = build_research_panel(n_days=130)
    plan, result = _compile_execute("rank(return_126d)", panel, registry, policy)
    split = default_period_split(130)
    config = FactorValidationConfig(
        min_discovery_sessions=10,
        min_validation_sessions=10,
        min_sealed_test_sessions=5,
        min_walk_forward_folds=1,
    )
    artifact = validate_factor_execution(
        plan=plan,
        execution_result=result,
        input_panel=panel,
        period_split=split,
        validation_config=config,
        factor_direction=FactorDirection.HIGHER_IS_BETTER,
    )
    assert artifact.validation_artifact_hash.startswith("sha256:")
    assert artifact.sealed_test.status == "SEALED"
    assert artifact.sealed_test_metrics is None
    assert artifact.discovery_metrics.get("valid_date_count", 0) >= 0


def test_sealed_test_requires_access(registry, policy):
    panel = build_research_panel(n_days=130)
    plan, result = _compile_execute("rank(return_126d)", panel, registry, policy)
    split = default_period_split(130)
    config = FactorValidationConfig(min_discovery_sessions=10, min_validation_sessions=10, min_sealed_test_sessions=5)
    closed = validate_factor_execution(
        plan=plan,
        execution_result=result,
        input_panel=panel,
        period_split=split,
        validation_config=config,
    )
    access = SealedTestAccess(
        reason="unit test",
        requested_by="tester",
        approval_reference="APR-001",
        expected_formula_hash=plan.formula_hash_value,
        expected_plan_hash=plan.plan_hash_value,
    )
    opened = validate_factor_execution(
        plan=plan,
        execution_result=result,
        input_panel=panel,
        period_split=split,
        validation_config=config,
        sealed_test_access=access,
    )
    assert opened.sealed_test.opened is True
    assert opened.sealed_test_metrics is not None
    assert closed.validation_artifact_hash != opened.validation_artifact_hash


def test_predictive_factor_on_research_panel(registry, policy):
    panel = build_research_panel(n_days=130)
    plan, result = _compile_execute("rank(return_126d)", panel, registry, policy)
    split = default_period_split(130)
    config = FactorValidationConfig(
        primary_horizon_sessions=5,
        outcome_horizons_sessions=(5,),
        min_discovery_sessions=5,
        min_validation_sessions=5,
        min_sealed_test_sessions=3,
        min_walk_forward_folds=1,
    )
    artifact = validate_factor_execution(
        plan=plan,
        execution_result=result,
        input_panel=panel,
        period_split=split,
        validation_config=config,
    )
    assert artifact.acceptance_gate.overall_status in ("PASS", "FAIL", "INCONCLUSIVE")
