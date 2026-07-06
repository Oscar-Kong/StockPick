"""Tests for derived field materialization."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.derived_fields import get_derived_field_spec, materialize_derived_field
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel


def test_return_1d_from_adjusted_close():
    panel = build_research_panel()
    primitives = {"adjusted_close": panel.frame["adjusted_close"]}
    series, prov = materialize_derived_field(
        "return_1d",
        primitives=primitives,
        index=panel.frame.index,
        provider_id="fixture",
    )
    assert prov.derivation_version == "return_pct_v1"
    assert series.notna().sum() > 0


def test_return_126d_warmup():
    panel = build_research_panel(n_days=130)
    primitives = {"adjusted_close": panel.frame["adjusted_close"]}
    series, _ = materialize_derived_field(
        "return_126d",
        primitives=primitives,
        index=panel.frame.index,
        provider_id="fixture",
    )
    per_sym = series.groupby(level="symbol").apply(lambda s: s.first_valid_index())
    assert per_sym.notna().all()


def test_relative_volume_requires_volume():
    panel = build_research_panel()
    with pytest.raises(Exception):
        materialize_derived_field(
            "relative_volume",
            primitives={"adjusted_close": panel.frame["adjusted_close"]},
            index=panel.frame.index,
            provider_id="fixture",
        )


def test_registry_has_expected_fields():
    assert get_derived_field_spec("return_1d") is not None
    assert get_derived_field_spec("return_126d") is not None
    assert get_derived_field_spec("relative_volume") is not None
