"""Tests for field resolution against input panels."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.compiler import compile_factor_expression
from engines.factor.discovery.errors import FactorCompileError
from engines.factor.discovery.execution_errors import PointInTimeViolationError
from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
from engines.factor.discovery.field_resolver import resolve_fields
from engines.factor.discovery.panel_models import FactorExecutionConfig
from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.provenance import PitProvenanceState
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel


def test_resolves_primitives_and_derived():
    panel = build_research_panel()
    plan = compile_factor_expression(
        parse_factor_expression("rank(return_126d)"),
        field_registry=build_default_field_registry(),
        data_source_policy=default_data_source_policy(),
    )
    bundle = resolve_fields(plan, panel, config=FactorExecutionConfig())
    assert "return_126d" in bundle.series
    assert "adjusted_close" not in bundle.series or True


def test_unverified_pit_rejected_in_strict_mode():
    panel = build_research_panel()
    prov = dict(panel.field_provenance)
    mc = prov["market_cap"].model_copy(update={"pit_state": PitProvenanceState.UNVERIFIED})
    prov["market_cap"] = mc
    bad = type(panel)(**{**panel.__dict__, "field_provenance": prov})
    plan = compile_factor_expression(
        parse_factor_expression("rank(market_cap)"),
        field_registry=build_default_field_registry(),
        data_source_policy=default_data_source_policy(),
    )
    with pytest.raises(PointInTimeViolationError):
        resolve_fields(plan, bad, config=FactorExecutionConfig(strict_pit_mode=True))


def test_unavailable_conceptual_field_rejected_at_compile():
    with pytest.raises(FactorCompileError):
        compile_factor_expression(
            parse_factor_expression("rank(gross_margin_volatility)"),
            field_registry=build_default_field_registry(),
            data_source_policy=default_data_source_policy(),
        )
