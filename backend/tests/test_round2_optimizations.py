"""Round 2 optimization tests — pillars, valuation, recommendation gates."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.data_confidence import build_data_confidence
from engines.recommendation.engine import build_recommendation
from engines.scoring.pillars import compute_pillar_scores
from engines.valuation.engine import run_dcf, reverse_dcf_implied_growth
from data.reconciler import ReconcileResult


def test_pillar_scores_composite():
    factors = [
        {"factor_id": "medium_rs_vs_spy", "norm_score": 80, "contribution": 14},
        {"factor_id": "medium_earnings_revision", "norm_score": 70, "contribution": 7},
    ]
    p = compute_pillar_scores(factors, valuation_score=55, catalyst_score=65, data_confidence=85)
    assert p.alpha_score > 0
    assert p.final_recommendation_score > 0


def test_dcf_produces_positive_fair_value():
    base, bull, bear = run_dcf(
        revenue=1_000_000_000,
        operating_margin=0.20,
        shares=100_000_000,
        revenue_cagr=0.10,
    )
    assert base > 0
    assert bull >= base
    assert bear <= base


def test_dcf_sensitivity_grid_shape():
    from engines.valuation.engine import dcf_sensitivity_grid

    g = dcf_sensitivity_grid(
        revenue=1_000_000_000,
        operating_margin=0.20,
        shares=100_000_000,
        revenue_cagr=0.10,
    )
    assert len(g["values"]) == len(g["wacc"])


def test_reverse_dcf_implied_growth():
    growth, margin = reverse_dcf_implied_growth(
        price=100,
        revenue=1_000_000_000,
        operating_margin=0.20,
        shares=100_000_000,
    )
    assert growth is not None
    assert margin is not None


def test_strong_buy_gated_by_data_confidence():
    from engines.data_confidence import DataConfidence

    dc = DataConfidence(score=65, issues=["stale fundamentals"])
    rec = build_recommendation(
        symbol="TEST",
        sleeve="medium",
        final_score=85,
        factors=[{"factor_id": "medium_rs_vs_spy", "norm_score": 85, "contribution": 15}],
        risk_score=30,
        risk_deduction=2,
        data_confidence=dc,
        valuation_score=60,
        catalyst_score=70,
        valuation_verdict="fair",
    )
    assert rec.label != "strong_buy"


def test_reconcile_result_quality():
    rec = ReconcileResult(symbol="AAPL", quality_score=75.0, flags=[])
    dc = build_data_confidence("AAPL", rec)
    assert dc.score == 75.0


def test_no_sizing_recursion():
    """build_position_sizing must not recurse into full build_v2_score sizing."""
    import inspect
    from services import quant_v2_service, quant_risk_sizing_service

    src = inspect.getsource(quant_v2_service.build_v2_score)
    assert "build_position_sizing(" not in src
    assert "include_sizing" in src

    src2 = inspect.getsource(quant_risk_sizing_service.build_position_sizing)
    assert "include_sizing=False" in src2


def test_trading_calendar_session_forward():
    import pytest
    from datetime import date

    from utils.trading_calendar import calendar_available, session_index_for_date

    if not calendar_available():
        pytest.skip("exchange_calendars not installed")
    idx = session_index_for_date(date(2024, 1, 2))
    assert idx is not None and idx >= 0


def test_factor_performance_shape():
    from engines.factors.performance import get_factor_performance

    out = get_factor_performance()
    assert "factors" in out
    assert "by_regime" in out
    assert "by_sector" in out


def test_pooled_ic_includes_by_sector():
    from engines.weighting.ic_panel import _pooled_ic

    stats = _pooled_ic("medium_rs_vs_spy", ["AAPL", "MSFT"], forward_days=5)
    if "ic" in stats:
        assert "by_sector" in stats


def test_find_today_snapshot_import():
    from engines.prediction.snapshots import find_today_snapshot, link_trade_to_snapshot

    assert callable(find_today_snapshot)
    assert callable(link_trade_to_snapshot)


if __name__ == "__main__":
    test_pillar_scores_composite()
    test_dcf_produces_positive_fair_value()
    test_dcf_sensitivity_grid_shape()
    test_reverse_dcf_implied_growth()
    test_strong_buy_gated_by_data_confidence()
    test_reconcile_result_quality()
    test_no_sizing_recursion()
    test_trading_calendar_session_forward()
    test_factor_performance_shape()
    test_find_today_snapshot_import()
    print("round2 tests ok")
