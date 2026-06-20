"""Quant Lab service integration tests with deterministic fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.pairs_research_service import run_pairs_research
from services.pairs_research_store import load_latest_pairs_run, persist_pairs_run
from services.quant_lab_summary_service import build_pairs_last_run, get_quant_lab_evidence
from services.walk_forward_research_service import cross_section_metrics, run_walk_forward_research, WalkForwardConfig
from tests.fixtures.quant_lab_fixtures import (
    build_cointegrated_panel,
    build_daily_ohlc,
    build_price_panel_8_symbols,
    seed_factor_ic,
    seed_pairs_run,
    seed_walk_forward_run,
)


def test_cross_section_metrics_without_scipy():
    scores = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    fwd = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    out = cross_section_metrics(scores, fwd)
    assert out["sufficient"] is True
    assert out["pearson_ic"] == pytest.approx(1.0, abs=1e-4)
    assert out["rank_ic"] == pytest.approx(1.0, abs=1e-4)


def test_pairs_persistence_roundtrip(isolated_backend_env):
    result = run_pairs_research(
        ["AAA", "BBB", "CCC"],
        price_panel=build_cointegrated_panel(),
    )
    run_id = persist_pairs_run(result)
    loaded = load_latest_pairs_run()
    assert loaded is not None
    assert loaded["run_id"] == run_id
    assert loaded["pairs_evaluated"] >= 1


def test_pairs_evidence_after_seed(isolated_backend_env):
    seed_pairs_run()
    card = build_pairs_last_run()
    assert card.available is True
    assert card.run_id == "pairs_test_001"


def test_walk_forward_synthetic_pipeline(isolated_backend_env):
    from datetime import date
    from types import SimpleNamespace
    from unittest.mock import patch

    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]
    panel = build_price_panel_8_symbols()
    as_of = date(2024, 6, 3)

    factor = SimpleNamespace(
        factor_id="momentum",
        display_name="Momentum",
        norm_score=50.0,
        weight=1.0,
        contribution=50.0,
    )
    scoring = SimpleNamespace(
        final_score=50.0,
        raw_score=50.0,
        regime_mult=1.0,
        sector_tilt=0.0,
        dq_multiplier=1.0,
        factors=[factor],
    )
    risk = SimpleNamespace(risk_score=25.0, deduction_pts=0.0, breakdown={"vol": 25.0})

    with (
        patch("services.walk_forward_research_service.rebalance_dates", return_value=[as_of]),
        patch("services.walk_forward_research_service.universe_for_date", return_value=(symbols, "pit")),
        patch("services.walk_forward_research_service.ScoringEngine.score", return_value=scoring),
        patch("services.walk_forward_research_service.RiskEngine.assess", return_value=risk),
        patch("services.walk_forward_research_service._forward_return_pct", return_value=0.05),
        patch("services.walk_forward_research_service.persist_walk_forward_run"),
        patch("services.walk_forward_research_service._persist_research_snapshot"),
    ):
        summary = run_walk_forward_research(
            WalkForwardConfig(
                sleeve="medium",
                start_date="2024-01-01",
                end_date="2024-06-30",
                forward_horizons=[5],
                persist_snapshots=False,
            ),
            price_panel={k: panel[k] for k in symbols},
            spy_hist=build_daily_ohlc("SPY", days=520),
        )
    assert summary["status"] == "completed"
    assert summary["periods_scored"] >= 1


def test_evidence_reflects_seeded_ic(isolated_backend_env):
    seed_factor_ic(sleeve="medium")
    seed_walk_forward_run()
    evidence = get_quant_lab_evidence(sleeve="medium")
    assert evidence.factor_ic.available is True
    assert evidence.walk_forward.available is True
