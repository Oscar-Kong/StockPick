"""Tests for Factor Discovery input panel contract."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.compiler import compile_factor_expression
from engines.factor.discovery.execution_errors import (
    AdjustedPriceViolationError,
    InvalidInputPanelError,
    PanelPolicyMismatchError,
)
from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
from engines.factor.discovery.panel_models import FactorInputPanel, validate_input_panel
from engines.factor.discovery.provenance import PanelFieldProvenance, PanelFieldSourceType, PitProvenanceState
from engines.factor.discovery.parser import parse_factor_expression
from models.schemas_factor_discovery import FieldNode
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel


def _minimal_panel(**kwargs) -> FactorInputPanel:
    idx = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2024-01-02"), "AAA"), (pd.Timestamp("2024-01-03"), "AAA")],
        names=["date", "symbol"],
    )
    frame = pd.DataFrame({"adjusted_close": [100.0, 101.0]}, index=idx)
    elig = pd.Series([True, True], index=idx)
    prov = {
        "adjusted_close": PanelFieldProvenance(
            field_id="adjusted_close",
            source_type=PanelFieldSourceType.SUPPLIED_PRIMITIVE,
            pit_state=PitProvenanceState.VERIFIED_PIT,
            provider_id="fixture",
            source_policy_id="research_adjusted_daily_v1",
            is_adjusted=True,
        )
    }
    return FactorInputPanel(
        frame=frame,
        eligibility=elig,
        data_source_policy_id="research_adjusted_daily_v1",
        provider_id="fixture",
        prices_adjusted=True,
        field_provenance=prov,
        **kwargs,
    )


def test_valid_panel_passes():
    panel = build_research_panel()
    plan = compile_factor_expression(
        FieldNode(field_id="adjusted_close"),
        field_registry=build_default_field_registry(),
        data_source_policy=default_data_source_policy(),
    )
    validate_input_panel(panel, plan=plan)


def test_duplicate_index_rejected():
    panel = _minimal_panel()
    dup = pd.concat([panel.frame, panel.frame.iloc[[0]]])
    bad = FactorInputPanel(
        frame=dup,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=True,
        field_provenance=panel.field_provenance,
    )
    with pytest.raises(InvalidInputPanelError, match="duplicate"):
        validate_input_panel(bad)


def test_empty_panel_rejected():
    panel = _minimal_panel()
    empty = FactorInputPanel(
        frame=panel.frame.iloc[:0],
        eligibility=panel.eligibility.iloc[:0],
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=True,
        field_provenance={},
        has_universe_membership=True,
    )
    with pytest.raises(InvalidInputPanelError, match="empty"):
        validate_input_panel(empty)


def test_policy_mismatch():
    panel = build_research_panel()
    plan = compile_factor_expression(
        FieldNode(field_id="adjusted_close"),
        field_registry=build_default_field_registry(),
    )
    bad = FactorInputPanel(
        frame=panel.frame,
        eligibility=panel.eligibility,
        data_source_policy_id="other_policy",
        provider_id=panel.provider_id,
        prices_adjusted=True,
        field_provenance=panel.field_provenance,
    )
    with pytest.raises(PanelPolicyMismatchError):
        validate_input_panel(bad, plan=plan)


def test_outcome_field_in_panel_rejected():
    panel = build_research_panel()
    frame = panel.frame.copy()
    frame["forward_return_5d"] = 0.01
    bad = FactorInputPanel(
        frame=frame,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=True,
        field_provenance=panel.field_provenance,
    )
    with pytest.raises(InvalidInputPanelError, match="outcome"):
        validate_input_panel(bad)


def test_non_finite_rejected():
    panel = _minimal_panel()
    frame = panel.frame.copy()
    frame.iloc[0, 0] = np.inf
    bad = FactorInputPanel(
        frame=frame,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=True,
        field_provenance=panel.field_provenance,
    )
    with pytest.raises(InvalidInputPanelError, match="non-finite"):
        validate_input_panel(bad)


def test_unadjusted_panel_rejected_for_adjusted_plan():
    panel = _minimal_panel()
    plan = parse_factor_expression("rank(return_126d)")
    compiled = compile_factor_expression(
        plan,
        field_registry=build_default_field_registry(),
        data_source_policy=default_data_source_policy(),
    )
    bad = FactorInputPanel(
        frame=panel.frame,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=False,
        field_provenance=panel.field_provenance,
    )
    with pytest.raises(AdjustedPriceViolationError):
        validate_input_panel(bad, plan=compiled)
