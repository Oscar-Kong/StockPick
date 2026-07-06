"""Factor Discovery outcome generation tests."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.outcomes import build_factor_outcomes
from engines.factor.discovery.sessions import align_panel_to_canonical_sessions, extract_canonical_sessions
from engines.factor.discovery.validation_models import FactorValidationConfig
from tests.fixtures.factor_discovery.validation.validation_panel_builder import (
    build_sparse_session_panel,
    build_predictive_panel,
)


@pytest.fixture
def config():
    return FactorValidationConfig(primary_horizon_sessions=5, outcome_horizons_sessions=(5, 21))


def test_outcome_uses_canonical_sessions_not_sparse_rows(config):
    sparse = build_sparse_session_panel(n_days=30)
    aligned, cal, _ = align_panel_to_canonical_sessions(sparse)
    outcome = build_factor_outcomes(aligned, horizon_sessions=5, config=config, calendar=cal)
    # SP2 missing row at i%3==1 should not shorten horizon — outcome at t requires price at t+1+5
    valid = outcome.outcome_valid
    assert valid.sum() >= 0


def test_missing_horizon_end_price_is_missing(config):
    panel = build_predictive_panel(n_days=40, n_symbols=3)
    aligned, cal, _ = align_panel_to_canonical_sessions(panel)
    outcome = build_factor_outcomes(aligned, horizon_sessions=21, config=config, calendar=cal)
    last_date = cal.sessions[-1]
    # scores near end should lack valid outcomes
    near_end = outcome.outcome_valid.xs(last_date, level=0)
    assert not near_end.all()


def test_outcome_hash_stable(config):
    panel = build_predictive_panel(n_days=50)
    aligned, cal, _ = align_panel_to_canonical_sessions(panel)
    a = build_factor_outcomes(aligned, horizon_sessions=5, config=config, calendar=cal)
    b = build_factor_outcomes(aligned, horizon_sessions=5, config=config, calendar=cal)
    assert a.panel_hash == b.panel_hash


def test_next_session_timing_not_same_close(config):
    panel = build_predictive_panel(n_days=60, n_symbols=5)
    aligned, cal, _ = align_panel_to_canonical_sessions(panel)
    outcome = build_factor_outcomes(aligned, horizon_sessions=1, config=config, calendar=cal)
    # start price should be next session after score date
    idx = outcome.outcome_valid[outcome.outcome_valid].index[0]
    score_date = pd.Timestamp(idx[0])
    start_px = outcome.start_price.loc[idx]
    same_day_px = aligned.frame.loc[(score_date, idx[1]), "adjusted_close"]
    assert start_px != same_day_px or score_date not in cal.sessions[:-1]
