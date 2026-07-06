"""Tests for execution provenance records."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.compiler import compile_factor_expression
from engines.factor.discovery.executor import compute_factor_panel
from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.provenance import PanelFieldSourceType, PitProvenanceState
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel


def test_derived_field_provenance_recorded():
    panel = build_research_panel(n_days=130)
    plan = compile_factor_expression(
        parse_factor_expression("rank(return_126d)"),
        field_registry=build_default_field_registry(),
        data_source_policy=default_data_source_policy(),
    )
    result = compute_factor_panel(plan, panel)
    assert len(result.derived_field_provenance) == 1
    prov = result.derived_field_provenance[0]
    assert prov.field_id == "return_126d"
    assert prov.source_type == PanelFieldSourceType.DERIVED
    assert prov.pit_state == PitProvenanceState.DERIVED_FROM_VERIFIED_PIT
    assert "adjusted_close" in prov.primitive_dependencies


def test_primitive_pit_provenance_on_fcf():
    panel = build_research_panel(n_days=130)
    plan = compile_factor_expression(
        parse_factor_expression("lag(free_cash_flow,1)"),
        field_registry=build_default_field_registry(),
        data_source_policy=default_data_source_policy(),
    )
    result = compute_factor_panel(plan, panel)
    fcf_prov = next(p for p in result.field_provenance if p.field_id == "free_cash_flow")
    assert fcf_prov.pit_state == PitProvenanceState.VERIFIED_PIT
    assert fcf_prov.publication_lag_sessions_applied == 45
