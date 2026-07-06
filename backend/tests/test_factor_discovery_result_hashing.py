"""Tests for Factor Discovery panel and execution hashing."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.panel_models import FactorExecutionConfig
from engines.factor.discovery.result_hashing import EXECUTOR_VERSION, execution_hash, hash_panel_content
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel


def test_panel_hash_stable_across_row_order():
    panel = build_research_panel()
    h1 = panel.content_hash
    shuffled = panel.frame.sample(frac=1.0, random_state=1)
    shuffled_elig = panel.eligibility.loc[shuffled.index]
    h2 = hash_panel_content(
        shuffled,
        eligibility=shuffled_elig,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
        panel_version=panel.panel_version,
    )
    assert h1 == h2


def test_panel_hash_changes_with_value():
    panel = build_research_panel()
    h1 = panel.content_hash
    frame = panel.frame.copy()
    frame.iloc[0, 0] = frame.iloc[0, 0] + 1.0
    h2 = hash_panel_content(
        frame,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
        panel_version=panel.panel_version,
    )
    assert h1 != h2


def test_panel_hash_changes_with_eligibility():
    panel = build_research_panel()
    h1 = panel.content_hash
    elig = panel.eligibility.copy()
    elig.iloc[0] = not bool(elig.iloc[0])
    h2 = hash_panel_content(
        panel.frame,
        eligibility=elig,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
        panel_version=panel.panel_version,
    )
    assert h1 != h2


def test_execution_hash_deterministic():
    panel = build_research_panel()
    config = FactorExecutionConfig()
    h1 = execution_hash(
        plan_hash_value="sha256:abc",
        panel_content_hash=panel.content_hash,
        config=config,
    )
    h2 = execution_hash(
        plan_hash_value="sha256:abc",
        panel_content_hash=panel.content_hash,
        config=config,
    )
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_execution_hash_sensitive_to_config():
    panel = build_research_panel()
    h1 = execution_hash(
        plan_hash_value="sha256:abc",
        panel_content_hash=panel.content_hash,
        config=FactorExecutionConfig(min_cross_sectional_observations=2),
    )
    h2 = execution_hash(
        plan_hash_value="sha256:abc",
        panel_content_hash=panel.content_hash,
        config=FactorExecutionConfig(min_cross_sectional_observations=3),
    )
    assert h1 != h2
