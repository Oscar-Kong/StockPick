"""Factor Discovery period resolution tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.periods import resolve_research_periods
from engines.factor.discovery.sessions import extract_canonical_sessions
from engines.factor.discovery.validation_models import FactorValidationConfig
from tests.fixtures.factor_discovery.validation.validation_panel_builder import (
    build_predictive_panel,
    default_period_split,
)


def test_resolve_three_period_split():
    panel = build_predictive_panel(n_days=90)
    cal = extract_canonical_sessions(panel.frame)
    split = default_period_split(90)
    config = FactorValidationConfig(min_discovery_sessions=5, min_validation_sessions=5, min_sealed_test_sessions=3)
    resolved = resolve_research_periods(split, cal, config=config)
    assert resolved.discovery_count > 0
    assert resolved.validation_count > 0
    assert resolved.sealed_test_count > 0
    assert not (set(resolved.discovery_sessions) & set(resolved.validation_sessions))


def test_embargo_sessions_excluded():
    panel = build_predictive_panel(n_days=90)
    cal = extract_canonical_sessions(panel.frame)
    split = default_period_split(90)
    config = FactorValidationConfig()
    resolved = resolve_research_periods(split, cal, config=config)
    all_assigned = set(resolved.discovery_sessions) | set(resolved.validation_sessions) | set(resolved.sealed_test_sessions)
    cal_set = {s.strftime("%Y-%m-%d") for s in cal.sessions}
    assert all_assigned <= cal_set
