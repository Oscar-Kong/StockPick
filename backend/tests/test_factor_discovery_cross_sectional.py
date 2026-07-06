"""Tests for cross-sectional operators."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.cross_sectional import apply_rank, apply_zscore
from engines.factor.discovery.panel_models import FactorExecutionConfig, OperatorDiagnosticsCollector
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel


def test_rank_by_date_only():
    panel = build_research_panel()
    values = panel.frame["adjusted_close"]
    elig = panel.eligibility
    diag = OperatorDiagnosticsCollector()
    ranked = apply_rank(values, elig, FactorExecutionConfig(), diag)
    dates = ranked.index.get_level_values(0).unique()
    for d in dates[:5]:
        day = ranked.xs(d, level=0)
        valid = day.dropna()
        if len(valid) >= 2:
            assert valid.min() >= 0.0
            assert valid.max() <= 1.0


def test_zscore_zero_variance_nan():
    panel = build_research_panel(n_days=5)
    idx = panel.frame.index
    const = pd.Series(5.0, index=idx)
    elig = pd.Series(True, index=idx)
    diag = OperatorDiagnosticsCollector()
    out = apply_zscore(const, elig, FactorExecutionConfig(zero_variance_zscore="nan"), diag)
    assert out.isna().all()
    assert diag.zero_variance_zscore_count > 0
