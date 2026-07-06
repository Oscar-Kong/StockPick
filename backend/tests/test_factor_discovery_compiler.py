"""Tests for Factor Discovery compiler."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.compiler import compile_factor_definition, compile_factor_expression
from engines.factor.discovery.errors import FactorCompileError, ForbiddenFieldError, UnsupportedNodeError
from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
from engines.factor.discovery.parser import parse_factor_expression
from models.schemas_factor_discovery import (
    AstNode,
    BinaryNode,
    BinaryOperator,
    ConditionalNode,
    CrossSectionNode,
    CrossSectionOperator,
    FactorDefinition,
    FactorDirection,
    FactorLifecycleStatus,
    FieldNode,
    NeutralizationKey,
    NeutralizeNode,
    RollingNode,
    RollingOperator,
    UnaryNode,
    UnaryOperator,
    collect_field_ids,
    formula_hash,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "factor_discovery"
AST_ADAPTER = TypeAdapter(AstNode)


def _load_ast(name: str) -> AstNode:
    raw = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return AST_ADAPTER.validate_python(raw)


@pytest.fixture
def registry():
    return build_default_field_registry()


@pytest.fixture
def policy():
    return default_data_source_policy()


def test_required_fields_sorted(registry, policy):
    expr = parse_factor_expression(_load_dsl_text("sector_neutral_composite.dsl"))
    plan = compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)
    assert plan.required_field_ids == sorted(plan.required_field_ids)
    assert set(plan.required_field_ids) == {"relative_volume", "return_1d"}


def _load_dsl_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").strip()


def test_cross_sectional_requirement(registry, policy):
    plan = compile_factor_expression(_load_ast("simple_field_rank.json"), field_registry=registry, data_source_policy=policy)
    assert plan.requires_cross_sectional


def test_time_series_requirement(registry, policy):
    plan = compile_factor_expression(_load_ast("lagged_momentum.json"), field_registry=registry, data_source_policy=policy)
    assert plan.requires_time_series_history


def test_neutralization_requirement(registry, policy):
    plan = compile_factor_expression(_load_ast("safe_division_fcf_mcap.json"), field_registry=registry, data_source_policy=policy)
    assert plan.requires_neutralization
    assert plan.neutralization_keys == [NeutralizationKey.SECTOR.value]


def test_pit_and_publication_lag(registry, policy):
    plan = compile_factor_expression(_load_ast("safe_division_fcf_mcap.json"), field_registry=registry, data_source_policy=policy)
    assert plan.requires_point_in_time_data
    assert plan.requires_publication_lag
    assert plan.min_publication_lag_by_field.get("free_cash_flow") == 45


def test_adjusted_pricing_required(registry, policy):
    plan = compile_factor_expression(_load_ast("lagged_momentum.json"), field_registry=registry, data_source_policy=policy)
    assert plan.requires_adjusted_pricing


def test_operators_collected(registry, policy):
    plan = compile_factor_expression(_load_ast("safe_division_fcf_mcap.json"), field_registry=registry, data_source_policy=policy)
    assert "BINARY:DIVIDE" in plan.operators_used
    assert "NEUTRALIZE:SECTOR" in plan.operators_used


def test_lookback_lag(registry, policy):
    expr = RollingNode(op=RollingOperator.LAG, window=21, child=FieldNode(field_id="adjusted_close"))
    plan = compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)
    assert plan.max_lookback_sessions == 21
    assert plan.max_lag_sessions == 21


def test_lookback_pct_change(registry, policy):
    expr = RollingNode(
        op=RollingOperator.PCT_CHANGE,
        window=126,
        child=FieldNode(field_id="adjusted_close"),
    )
    plan = compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)
    assert plan.max_lookback_sessions == 126


def test_lookback_nested_rolling(registry, policy):
    inner = RollingNode(
        op=RollingOperator.PCT_CHANGE,
        window=21,
        child=FieldNode(field_id="adjusted_close"),
    )
    expr = RollingNode(op=RollingOperator.ROLLING_MEAN, window=63, child=inner)
    plan = compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)
    assert plan.max_lookback_sessions == 84


def test_lookback_lag_over_rolling(registry, policy):
    inner = RollingNode(op=RollingOperator.ROLLING_MEAN, window=63, child=FieldNode(field_id="adjusted_close"))
    expr = RollingNode(op=RollingOperator.LAG, window=21, child=inner)
    plan = compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)
    assert plan.max_lookback_sessions == 84


def test_lookback_rolling_correlation(registry, policy):
    left = RollingNode(op=RollingOperator.PCT_CHANGE, window=10, child=FieldNode(field_id="return_1d"))
    right = RollingNode(op=RollingOperator.LAG, window=5, child=FieldNode(field_id="relative_volume"))
    expr = RollingNode(op=RollingOperator.ROLLING_CORRELATION, window=20, child=left, right=right)
    plan = compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)
    assert plan.max_lookback_sessions == 30


def test_outcome_field_rejected(registry, policy):
    with pytest.raises(ForbiddenFieldError):
        compile_factor_expression(FieldNode(field_id="target_return"), field_registry=registry, data_source_policy=policy)


def test_conditional_rejected(registry, policy):
    cond = BinaryNode(
        op=BinaryOperator.ADD,
        left=FieldNode(field_id="return_1d"),
        right=FieldNode(field_id="return_126d"),
    )
    expr = ConditionalNode(condition=cond, if_true=FieldNode(field_id="return_1d"), if_false=FieldNode(field_id="return_126d"))
    with pytest.raises(UnsupportedNodeError):
        compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)


def test_required_fields_mismatch_on_definition(registry, policy):
    expr = _load_ast("simple_field_rank.json")
    defn = FactorDefinition(
        factor_id="disc_test",
        version="1.0.0",
        display_name="t",
        expression=expr,
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="penny",
        rebalance_frequency="weekly",
        holding_period_sessions=5,
        required_fields=["return_126d", "close"],
        lifecycle_status=FactorLifecycleStatus.DRAFT,
    )
    with pytest.raises(FactorCompileError, match="required_fields_mismatch"):
        compile_factor_definition(defn, field_registry=registry, data_source_policy=policy)


def test_compile_factor_definition_from_fixture(registry, policy):
    raw = json.loads((FIXTURES / "full_factor_definition.json").read_text())
    defn = FactorDefinition.model_validate(raw)
    plan = compile_factor_definition(defn, field_registry=registry, data_source_policy=policy)
    assert plan.formula_hash_value == defn.formula_hash()
    assert defn.lifecycle_status == FactorLifecycleStatus.DRAFT


def test_compiler_does_not_mutate_definition(registry, policy):
    raw = json.loads((FIXTURES / "full_factor_definition.json").read_text())
    defn = FactorDefinition.model_validate(raw)
    before = defn.model_dump()
    compile_factor_definition(defn, field_registry=registry, data_source_policy=policy)
    assert defn.model_dump() == before


def test_deterministic_plan(registry, policy):
    expr = _load_ast("lagged_momentum.json")
    p1 = compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)
    p2 = compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)
    assert p1.plan_hash_value == p2.plan_hash_value
    assert p1.canonical_dsl == p2.canonical_dsl


def test_plan_hash_differs_from_formula_hash(registry, policy):
    plan = compile_factor_expression(_load_ast("simple_field_rank.json"), field_registry=registry, data_source_policy=policy)
    assert plan.plan_hash_value != plan.formula_hash_value


def test_plan_hash_sensitive_to_registry_version(registry, policy):
    expr = _load_ast("simple_field_rank.json")
    p1 = compile_factor_expression(expr, field_registry=registry, data_source_policy=policy)
    other = registry.model_copy(update={"version": "factor-field-registry-v2"})
    p2 = compile_factor_expression(expr, field_registry=other, data_source_policy=policy)
    assert p1.plan_hash_value != p2.plan_hash_value


def test_golden_fixtures_compile_except_close(registry, policy):
    for name in (
        "simple_field_rank.json",
        "lagged_momentum.json",
        "safe_division_fcf_mcap.json",
        "sector_neutral_composite.json",
    ):
        compile_factor_expression(_load_ast(name), field_registry=registry, data_source_policy=policy)


def test_nested_rolling_close_rejected_by_policy(registry, policy):
    with pytest.raises(FactorCompileError, match="policy_incompatible"):
        compile_factor_expression(_load_ast("nested_rolling.json"), field_registry=registry, data_source_policy=policy)


def test_canonical_dsl_round_trip_hash(registry, policy):
    for name in ("lagged_momentum.json", "safe_division_fcf_mcap.json"):
        ast = _load_ast(name)
        plan = compile_factor_expression(ast, field_registry=registry, data_source_policy=policy)
        reparsed = parse_factor_expression(plan.canonical_dsl)
        assert formula_hash(reparsed) == plan.formula_hash_value
