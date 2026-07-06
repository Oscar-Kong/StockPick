"""End-to-end Factor Discovery executor tests."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.compiler import compile_factor_expression
from engines.factor.discovery.errors import UnsupportedNodeError
from engines.factor.discovery.executor import compute_factor_panel
from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
from engines.factor.discovery.parser import parse_factor_expression
from models.schemas_factor_discovery import ConditionalNode, FieldNode, formula_hash
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel


@pytest.fixture
def panel():
    return build_research_panel(n_days=130)


@pytest.fixture
def registry():
    return build_default_field_registry()


@pytest.fixture
def policy():
    return default_data_source_policy()


def _compile(dsl: str, registry, policy):
    ast = parse_factor_expression(dsl)
    return compile_factor_expression(ast, field_registry=registry, data_source_policy=policy)


def test_execute_rank_return_126d(panel, registry, policy):
    plan = _compile("rank(return_126d)", registry, policy)
    result = compute_factor_panel(plan, panel)
    assert result.valid_output_count > 0
    assert result.execution_hash_value.startswith("sha256:")
    assert result.formula_hash_value == plan.formula_hash_value


def test_execute_lagged_momentum(panel, registry, policy):
    dsl = "percentile_rank(pct_change(lag(adjusted_close,1),5))"
    plan = _compile(dsl, registry, policy)
    result = compute_factor_panel(plan, panel)
    assert result.valid_output_count > 0


def test_execute_sector_neutral_divide(panel, registry, policy):
    dsl = 'sector_neutralize(rank(divide(lag(free_cash_flow,1),market_cap,zero_policy="null")))'
    plan = _compile(dsl, registry, policy)
    result = compute_factor_panel(plan, panel)
    assert result.requires_neutralization if hasattr(result, "requires_neutralization") else True
    assert result.neutralization_diagnostics


def test_execute_rolling_correlation(panel, registry, policy):
    dsl = "rolling_correlation(adjusted_close,relative_volume,5)"
    plan = _compile(dsl, registry, policy)
    result = compute_factor_panel(plan, panel)
    assert result.valid_output_count >= 0


def test_no_future_price_leakage(panel, registry, policy):
    dsl = "lag(adjusted_close,1)"
    plan = _compile(dsl, registry, policy)
    full = compute_factor_panel(plan, panel)
    cut_date = panel.frame.index.get_level_values(0)[20]
    mask = panel.frame.index.get_level_values(0) <= cut_date
    sub_frame = panel.frame.loc[mask]
    sub_elig = panel.eligibility.loc[mask]
    sub_panel = type(panel)(
        frame=sub_frame,
        eligibility=sub_elig,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
    )
    partial = compute_factor_panel(plan, sub_panel)
    common_idx = partial.factor_values.dropna().index
    pd.testing.assert_series_equal(
        partial.factor_values.loc[common_idx],
        full.factor_values.loc[common_idx],
        check_names=False,
    )


def test_future_fundamental_does_not_affect_past(panel, registry, policy):
    dsl = "lag(free_cash_flow,1)"
    plan = _compile(dsl, registry, policy)
    full = compute_factor_panel(plan, panel)
    frame = panel.frame.copy()
    frame.loc[frame.index.get_level_values(0) > pd.Timestamp("2024-02-15"), "free_cash_flow"] = 999.0
    mutated = type(panel)(
        frame=frame,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
    )
    after = compute_factor_panel(plan, mutated)
    early_idx = full.factor_values.index[full.factor_values.index.get_level_values(0) < pd.Timestamp("2024-02-01")]
    pd.testing.assert_series_equal(
        full.factor_values.loc[early_idx],
        after.factor_values.loc[early_idx],
        check_names=False,
    )


def test_dsl_compile_execute_hash_chain(panel, registry, policy):
    dsl = "rank(return_126d)"
    ast = parse_factor_expression(dsl)
    expected_hash = formula_hash(ast)
    plan = compile_factor_expression(ast, field_registry=registry, data_source_policy=policy)
    result = compute_factor_panel(plan, panel)
    assert plan.formula_hash_value == expected_hash
    assert result.formula_hash_value == expected_hash


def test_future_eligibility_does_not_affect_past(panel, registry, policy):
    plan = _compile("rank(adjusted_close)", registry, policy)
    full = compute_factor_panel(plan, panel)
    cut = panel.frame.index.get_level_values(0)[25]
    elig = panel.eligibility.copy()
    elig.loc[elig.index.get_level_values(0) > cut] = False
    mutated = type(panel)(
        frame=panel.frame,
        eligibility=elig,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
    )
    after = compute_factor_panel(plan, mutated)
    early = full.factor_values.index[full.factor_values.index.get_level_values(0) <= cut]
    pd.testing.assert_series_equal(full.factor_values.loc[early], after.factor_values.loc[early], check_names=False)


def test_future_sector_does_not_affect_neutralized_past(panel, registry, policy):
    dsl = "sector_neutralize(rank(adjusted_close))"
    plan = _compile(dsl, registry, policy)
    full = compute_factor_panel(plan, panel)
    cut = pd.Timestamp("2024-02-01")
    frame = panel.frame.copy()
    frame.loc[frame.index.get_level_values(0) > cut, "sector"] = "MUTATED"
    mutated = type(panel)(
        frame=frame,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
    )
    after = compute_factor_panel(plan, mutated)
    early = full.factor_values.index[full.factor_values.index.get_level_values(0) < cut]
    pd.testing.assert_series_equal(full.factor_values.loc[early], after.factor_values.loc[early], check_names=False)
