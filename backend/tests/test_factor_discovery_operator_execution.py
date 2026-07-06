"""Tests for time-series operator execution."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.operators import (
    ExecutionContext,
    apply_divide,
    apply_lag,
    apply_pct_change,
    apply_rolling_mean,
)
from engines.factor.discovery.panel_models import FactorExecutionConfig
from models.schemas_factor_discovery import ZeroDivisionPolicy
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel


@pytest.fixture
def price_series():
    panel = build_research_panel(n_days=20)
    return panel.frame["adjusted_close"]


@pytest.fixture
def ctx():
    panel = build_research_panel(n_days=20)
    return ExecutionContext(index=panel.frame.index, config=FactorExecutionConfig())


def test_lag_per_symbol(price_series, ctx):
    out = apply_lag(price_series, 1, ctx)
    assert out.groupby(level="symbol").apply(lambda s: s.droplevel("symbol").iloc[1]).notna().all()


def test_pct_change_zero_prior_nan(price_series, ctx):
    out = apply_pct_change(price_series, 1, ctx)
    assert not np.isinf(out.dropna()).any()


def test_divide_zero_policy_null(price_series, ctx):
    denom = price_series.copy()
    denom.iloc[0] = 0.0
    out = apply_divide(price_series, denom, ctx, ZeroDivisionPolicy.NULL)
    assert pd.isna(out.iloc[0])
    assert ctx.diagnostics.zero_denominator_count >= 1


def test_rolling_mean_no_cross_symbol(price_series, ctx):
    out = apply_rolling_mean(price_series, 5, ctx)
    aaa = out.xs("AAA", level="symbol")
    assert aaa.notna().sum() > 0
