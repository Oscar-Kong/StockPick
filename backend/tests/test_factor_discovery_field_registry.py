"""Tests for Factor Discovery field registry."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.compiler import compile_factor_expression
from engines.factor.discovery.errors import FactorCompileError, ForbiddenFieldError, UnknownFieldError
from engines.factor.discovery.field_registry import (
    FactorFieldSpec,
    FieldAvailability,
    FieldTemporalScope,
    build_default_field_registry,
    default_data_source_policy,
)
from models.schemas_factor_discovery import FieldNode, InputDataClass


@pytest.fixture
def registry():
    return build_default_field_registry()


def test_known_permitted_field(registry):
    spec = registry.require("adjusted_close")
    assert spec.factor_input_allowed
    assert spec.requires_adjusted_price


def test_unknown_field_rejected(registry):
    with pytest.raises(UnknownFieldError):
        compile_factor_expression(
            FieldNode(field_id="not_a_real_field"),
            field_registry=registry,
        )


def test_forbidden_outcome_field(registry):
    with pytest.raises(ForbiddenFieldError, match="forward_return_5d"):
        compile_factor_expression(
            FieldNode(field_id="forward_return_5d"),
            field_registry=registry,
        )


def test_unavailable_field(registry):
    with pytest.raises(FactorCompileError, match="unavailable_field"):
        compile_factor_expression(
            FieldNode(field_id="gross_margin_volatility"),
            field_registry=registry,
        )


def test_point_in_time_metadata(registry):
    spec = registry.require("free_cash_flow")
    assert spec.requires_point_in_time
    assert spec.requires_publication_lag
    assert spec.min_publication_lag_sessions == 45


def test_adjusted_price_metadata(registry):
    spec = registry.require("return_126d")
    assert spec.requires_adjusted_price


def test_registry_version_stable(registry):
    assert registry.version == "factor-field-registry-v1"


def test_duplicate_registration_rejected():
    base = build_default_field_registry()
    extra = FactorFieldSpec(
        field_id="adjusted_close",
        display_label="dup",
        data_class=InputDataClass.PRICE,
        description="dup",
    )
    with pytest.raises(ValueError, match="duplicate"):
        build_default_field_registry(extra_fields=[extra])


def test_policy_contract():
    policy = default_data_source_policy()
    assert policy.policy_id == "research_adjusted_daily_v1"
    assert policy.adjusted_prices_required


def test_close_incompatible_with_research_policy(registry):
    with pytest.raises(FactorCompileError, match="policy_incompatible"):
        compile_factor_expression(
            FieldNode(field_id="close"),
            field_registry=registry,
            data_source_policy=default_data_source_policy(),
        )


def test_derived_panel_field_compiles_with_warning(registry):
    plan = compile_factor_expression(
        FieldNode(field_id="return_126d"),
        field_registry=registry,
    )
    assert any("derived panel" in w for w in plan.warnings)
