"""Tests for neutralization operators."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.neutralization import neutralize_sector
from engines.factor.discovery.panel_models import FactorExecutionConfig
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel


def test_sector_demean_reduces_group_mean():
    panel = build_research_panel()
    values = panel.frame["adjusted_close"]
    sector = panel.frame["sector"]
    out, _diag = neutralize_sector(values, sector, FactorExecutionConfig(min_neutralization_group_size=2))
    tmp = out.to_frame("v")
    tmp["sector"] = sector.values
    tmp["td"] = tmp.index.get_level_values(0)
    for (_d, sec), grp in tmp.dropna().groupby(["td", "sector"]):
        if len(grp) >= 2:
            assert abs(grp["v"].mean()) < 1e-9


def test_small_sector_group_nan():
    panel = build_research_panel()
    values = panel.frame["adjusted_close"]
    sector = panel.frame["sector"]
    out, diag = neutralize_sector(values, sector, FactorExecutionConfig(min_neutralization_group_size=2))
    solo = out[sector == "SOLO"]
    assert solo.isna().all()
