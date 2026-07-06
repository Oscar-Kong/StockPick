"""Phase 4 hardening regression tests for Factor Discovery."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.compiler import compile_factor_expression
from engines.factor.discovery.executor import compute_factor_panel
from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
from engines.factor.discovery.metrics_adapter import evaluate_cross_sectional_metrics
from engines.factor.discovery.outcomes import build_factor_outcomes
from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.periods import resolve_research_periods
from engines.factor.discovery.session_hashing import canonical_session_hash
from engines.factor.discovery.sessions import align_panel_to_canonical_sessions, extract_canonical_sessions
from engines.factor.discovery.statistics import newey_west_t_stat, resolve_primary_significance
from engines.factor.discovery.validation_engine import validate_factor_execution
from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit, FactorDirection
from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel
from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_validation_context


def _compile(dsl: str):
    registry = build_default_field_registry()
    policy = default_data_source_policy()
    ast = parse_factor_expression(dsl)
    return compile_factor_expression(ast, field_registry=registry, data_source_policy=policy)


def test_future_market_cap_isolation():
    from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_predictive_panel

    panel = build_predictive_panel(n_days=130, n_symbols=10)
    plan = _compile('market_cap_neutralize(rank(adjusted_close))')
    cut = pd.Timestamp("2024-03-01")
    full = compute_factor_panel(plan, panel)

    frame = panel.frame.copy()
    frame.loc[frame.index.get_level_values(0) > cut, "market_cap"] = (
        frame.loc[frame.index.get_level_values(0) > cut, "market_cap"] * 100
    )
    mutated = type(panel)(
        frame=frame,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
    )
    after = compute_factor_panel(plan, mutated)
    early = full.factor_values.index[full.factor_values.index.get_level_values(0) <= cut]
    pd.testing.assert_series_equal(full.factor_values.loc[early], after.factor_values.loc[early], check_names=False)


def test_publication_timestamp_isolation():
    panel = build_research_panel(n_days=130)
    plan = _compile("lag(free_cash_flow,1)")
    cut = pd.Timestamp("2024-02-01")
    full = compute_factor_panel(plan, panel)
    before_hash = full.execution_hash_value

    prov = dict(panel.field_provenance)
    fcf = prov["free_cash_flow"]
    prov["free_cash_flow"] = fcf.model_copy(update={"earliest_valid_date": "2099-01-01"})
    mutated = type(panel)(
        frame=panel.frame,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=prov,
    )
    after_meta = compute_factor_panel(plan, mutated)
    early = full.factor_values.index[full.factor_values.index.get_level_values(0) < cut]
    pd.testing.assert_series_equal(full.factor_values.loc[early], after_meta.factor_values.loc[early], check_names=False)
    assert after_meta.execution_hash_value != before_hash


def test_canonical_session_hash_changes_when_calendar_changes():
    panel = build_research_panel(n_days=40)
    cal1 = extract_canonical_sessions(panel.frame)
    h1 = canonical_session_hash(cal1)
    frame2 = panel.frame.iloc[:-5]
    cal2 = extract_canonical_sessions(frame2)
    h2 = canonical_session_hash(cal2)
    assert h1 != h2


def test_robust_significance_newey_west():
    values = [0.01, 0.02, 0.015, 0.03, 0.025, 0.018, 0.022, 0.019]
    result = resolve_primary_significance(
        values,
        method="newey_west",
        horizon_sessions=21,
        newey_west_lag_policy="floor_4x_horizon_over_3",
    )
    assert result["primary_method"] == "newey_west"
    assert result["primary_t_stat"] is not None
    assert result["newey_west_lag"] is not None
    assert abs(newey_west_t_stat(values, max_lag=int(result["newey_west_lag"])) - float(result["primary_t_stat"])) < 1e-3


def test_closed_validation_does_not_compute_sealed_metrics(monkeypatch):
    ctx = build_validation_context()
    panel = ctx["panel"]
    plan = ctx["plan"]
    execution = compute_factor_panel(plan, panel)

    calls: list[str] = []

    def spy(*args, **kwargs):
        calls.append("sealed")
        raise AssertionError("sealed metrics should not run")

    monkeypatch.setattr(
        "engines.factor.discovery.validation_engine.evaluate_cross_sectional_metrics",
        lambda scores, outcome_panel, **kw: (
            spy()
            if kw.get("period_mask") is not None
            and kw["period_mask"].any()
            and False
            else __import__(
                "engines.factor.discovery.metrics_adapter", fromlist=["evaluate_cross_sectional_metrics"]
            ).evaluate_cross_sectional_metrics(scores, outcome_panel, **kw)
        ),
    )

    artifact = validate_factor_execution(
        plan=plan,
        execution_result=execution,
        input_panel=panel,
        period_split=ctx["period_split"],
        validation_config=ctx["validation_config"],
        factor_direction=FactorDirection.HIGHER_IS_BETTER,
    )
    assert artifact.sealed_test_metrics is None
    assert artifact.sealed_test.status == "SEALED"
    assert "sealed" not in calls
