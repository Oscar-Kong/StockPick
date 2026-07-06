"""Deterministic validation fixtures for Factor Discovery Phase 4."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from engines.factor.discovery.panel_models import FactorInputPanel
from engines.factor.discovery.provenance import PanelFieldProvenance, PanelFieldSourceType, PitProvenanceState
from models.schemas_factor_discovery import DiscoveryPeriodSplit


def _trading_dates(n: int, start: date = date(2024, 1, 2)) -> list[date]:
    out: list[date] = []
    cur = start
    while len(out) < n:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def _base_provenance(provider: str, policy: str) -> dict[str, PanelFieldProvenance]:
    def _p(fid: str, st: PanelFieldSourceType, **kw) -> PanelFieldProvenance:
        return PanelFieldProvenance(
            field_id=fid,
            source_type=st,
            pit_state=PitProvenanceState.VERIFIED_PIT,
            provider_id=provider,
            source_policy_id=policy,
            **kw,
        )

    return {
        "adjusted_close": _p("adjusted_close", PanelFieldSourceType.SUPPLIED_PRIMITIVE, is_adjusted=True),
        "volume": _p("volume", PanelFieldSourceType.SUPPLIED_PRIMITIVE),
        "market_cap": _p("market_cap", PanelFieldSourceType.EXPOSURE),
        "sector": _p("sector", PanelFieldSourceType.CLASSIFICATION),
        "signal": _p("signal", PanelFieldSourceType.SUPPLIED_PRIMITIVE),
    }


def build_predictive_panel(*, n_days: int = 90, n_symbols: int = 8, seed: int = 7) -> FactorInputPanel:
    """Scores in `signal` correlate with next-session returns."""
    rng = np.random.default_rng(seed)
    symbols = [f"S{i:02d}" for i in range(n_symbols)]
    dates = _trading_dates(n_days)
    rows = []
    for i, d in enumerate(dates):
        for j, sym in enumerate(symbols):
            ret = rng.normal(0.001, 0.02)
            price = 100 * (1.01 ** i) * (1 + j * 0.01) * (1 + ret)
            fwd_hint = rng.normal(0, 0.01)
            signal = fwd_hint + rng.normal(0, 0.005)
            rows.append(
                {
                    "date": pd.Timestamp(d),
                    "symbol": sym,
                    "adjusted_close": price,
                    "volume": 1_000_000,
                    "market_cap": price * 1e6,
                    "sector": "TECH" if j % 2 == 0 else "FIN",
                    "signal": signal,
                    "eligible": True,
                }
            )
    frame = pd.DataFrame(rows).set_index(["date", "symbol"]).sort_index()
    # inject predictive relationship into signal from realized forward returns
    for sym in symbols:
        sub = frame.xs(sym, level=1)
        fwd = sub["adjusted_close"].pct_change(5).shift(-5)
        frame.loc[(slice(None), sym), "signal"] = fwd.fillna(0) + rng.normal(0, 0.001, len(sub))

    eligibility = frame["eligible"].astype(bool)
    frame = frame.drop(columns=["eligible"])
    policy, provider = "research_adjusted_daily_v1", "fixture_provider_v1"
    return FactorInputPanel(
        frame=frame,
        eligibility=eligibility,
        data_source_policy_id=policy,
        provider_id=provider,
        prices_adjusted=True,
        field_provenance=_base_provenance(provider, policy),
    )


def build_sparse_session_panel(*, n_days: int = 30) -> FactorInputPanel:
    """One symbol missing intermittent sessions."""
    dates = _trading_dates(n_days)
    symbols = ["SP1", "SP2"]
    rows = []
    for i, d in enumerate(dates):
        for sym in symbols:
            if sym == "SP2" and i % 3 == 1:
                continue
            rows.append(
                {
                    "date": pd.Timestamp(d),
                    "symbol": sym,
                    "adjusted_close": 50.0 + i + (0 if sym == "SP1" else 5),
                    "volume": 1000,
                    "market_cap": 1e9,
                    "sector": "TECH",
                    "eligible": True,
                }
            )
    frame = pd.DataFrame(rows).set_index(["date", "symbol"]).sort_index()
    eligibility = pd.Series(True, index=frame.index)
    policy, provider = "research_adjusted_daily_v1", "fixture_provider_v1"
    prov = _base_provenance(provider, policy)
    return FactorInputPanel(
        frame=frame,
        eligibility=eligibility,
        data_source_policy_id=policy,
        provider_id=provider,
        prices_adjusted=True,
        field_provenance=prov,
    )


def default_period_split(n_days: int = 90) -> DiscoveryPeriodSplit:
    dates = _trading_dates(n_days)
    d_end = dates[-1]
    n = len(dates)
    i1 = n // 3
    i2 = 2 * n // 3
    return DiscoveryPeriodSplit(
        discovery_start=dates[0],
        discovery_end=dates[i1 - 1],
        validation_start=dates[i1],
        validation_end=dates[i2 - 1],
        sealed_test_start=dates[i2],
        sealed_test_end=d_end,
        embargo_days=0,
        min_sealed_test_days=1,
    )


def build_validation_context(*, n_days: int = 130):
    from engines.factor.discovery.compiler import compile_factor_expression
    from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
    from engines.factor.discovery.parser import parse_factor_expression
    from engines.factor.discovery.validation_models import FactorValidationConfig
    from tests.fixtures.factor_discovery.panels.research_panel_builder import build_research_panel

    panel = build_research_panel(n_days=n_days)
    registry = build_default_field_registry()
    policy = default_data_source_policy()
    dsl = "rank(return_126d)"
    plan = compile_factor_expression(parse_factor_expression(dsl), field_registry=registry, data_source_policy=policy)
    split = default_period_split(n_days)
    config = FactorValidationConfig(
        min_discovery_sessions=10,
        min_validation_sessions=10,
        min_sealed_test_sessions=5,
        min_walk_forward_folds=1,
        declared_hypothesis_family_size=1,
    )
    return {
        "panel": panel,
        "plan": plan,
        "period_split": split,
        "validation_config": config,
    }
