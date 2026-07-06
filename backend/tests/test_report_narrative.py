"""Tests for quant-driven AI report narrative (no rating override)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models.schemas_v2 as schemas_v2

schemas_v2.V2ScoreResponse.update_forward_refs()

from models.schemas_v2 import (
    DataConfidenceV2,
    FactorContributionV2,
    PillarScoresV2,
    RecommendationV2,
    RiskBreakdownV2,
    ScoreAttributionV2,
    V2ScoreResponse,
)
from services.report_llm_context import (
    RECOMMENDATION_TO_RATING_ACTION,
    build_quant_report_context,
    system_rating_from_score,
)
from services.report_narrative import DISCLAIMER_FOOTER, generate_report_narrative


def _mock_score() -> V2ScoreResponse:
    return V2ScoreResponse(
        symbol="TEST",
        sleeve="penny",
        score=72.0,
        market_regime="risk_on",
        summary="Momentum and quality supportive.",
        factors=[
            FactorContributionV2(
                factor_id="momentum",
                display_name="Momentum",
                norm_score=75.0,
                weight=0.3,
                contribution=22.5,
            )
        ],
        attribution=ScoreAttributionV2(
            raw_score=70.0,
            regime_mult=1.05,
            sector_tilt=0.0,
            dq_multiplier=0.98,
            openbb_delta=0.0,
            score_after_regime=73.5,
            score_after_dq=72.0,
            risk_deduction=0.0,
            final_score=72.0,
        ),
        risk=RiskBreakdownV2(
            risk_score=35.0,
            deduction_pts=0.0,
            items=[{"category": "event", "detail": "Low event risk"}],
        ),
        recommendation=RecommendationV2(
            recommendation="buy",
            confidence=72.0,
            time_horizon_days=60,
            expected_return_pct=8.0,
            expected_downside_pct=5.0,
            pillars=PillarScoresV2(
                alpha_score=75.0,
                valuation_score=55.0,
                catalyst_score=60.0,
                final_recommendation_score=72.0,
            ),
            data_confidence=DataConfidenceV2(data_confidence=85.0),
            gates=[],
            bull_case="Factor momentum strong.",
            bear_case="Valuation not cheap.",
        ),
        risk_level="medium",
        strategy_version="test",
        factor_model_version="test",
    )


def test_system_rating_from_recommendation_engine():
    score = _mock_score()
    rating = system_rating_from_score(score, sleeve="penny")
    assert rating["action"] == RECOMMENDATION_TO_RATING_ACTION["buy"]
    assert rating["system_label"] == "buy"
    assert rating["conviction"] == 72.0
    assert rating["source"] == "recommendation_engine"


def test_system_rating_fallback_without_recommendation():
    score = _mock_score()
    score.recommendation = None
    rating = system_rating_from_score(score, sleeve="penny")
    assert rating["action"] == "hold"
    assert rating["system_label"] == "unavailable"
    assert rating["source"] == "score_fallback"


@patch("services.report_llm_context._load_diagnostics")
def test_build_quant_report_context_shape(mock_diag):
    mock_diag.return_value = {"interpretation": "mostly noise", "sufficient_data": True}
    score = _mock_score()
    rec = SimpleNamespace(quality_score=80.0, flags=["peers_missing"])
    ctx = build_quant_report_context(score, sleeve="penny", reconcile=rec, include_diagnostics=True)

    assert ctx["symbol"] == "TEST"
    assert "system_rating" in ctx
    assert "score_attribution" in ctx
    assert "risk_breakdown" in ctx
    assert ctx["diagnostics_summary"]["interpretation"] == "mostly noise"
    assert ctx["data_quality"]["reconcile_quality_score"] == 80.0


def test_generate_report_narrative_rules_fallback():
    ctx = build_quant_report_context(_mock_score(), sleeve="penny", include_diagnostics=False)
    with patch("services.report_narrative.LLM_ENABLED", False):
        out = generate_report_narrative(ctx)
    assert out["source"] == "rules"
    assert "executive_summary" in out
    assert out["disclaimer"] == DISCLAIMER_FOOTER
    assert len(out["what_would_change_my_mind"]) >= 1
    assert len(out["data_quality_limitations"]) >= 1
    assert "buy" in out["executive_summary"].lower() or "72" in out["executive_summary"]


@patch("services.llm_explainer._call_llm")
def test_generate_report_narrative_llm_does_not_add_rating(mock_llm):
    mock_llm.return_value = (
        '{"executive_summary":"System label buy at 72.",'
        '"investment_thesis":{"bull_case":"a","bear_case":"b","edge":"c"},'
        '"uncertainty":["x"],'
        '"what_would_change_my_mind":["y"],'
        '"data_quality_limitations":["z"]}'
    )
    with patch("services.report_narrative.LLM_ENABLED", True), patch(
        "services.report_narrative.LLM_API_KEY", "test-key"
    ):
        out = generate_report_narrative(build_quant_report_context(_mock_score(), sleeve="penny"))
    assert out["source"] == "llm"
    assert "buy" in out["executive_summary"].lower()
    assert "action" not in out


@patch("services.report_narrative.generate_report_narrative")
def test_llm_explainer_uses_quant_context(mock_narrative):
    from services.llm_explainer import generate_explanation

    mock_narrative.return_value = {
        "executive_summary": "Explains buy.",
        "investment_thesis": {"bull_case": "a", "bear_case": "b", "edge": "c"},
        "uncertainty": [],
        "what_would_change_my_mind": ["Better data"],
        "data_quality_limitations": ["Stale peers"],
        "disclaimer": DISCLAIMER_FOOTER,
        "source": "rules",
    }
    ctx = build_quant_report_context(_mock_score(), sleeve="penny")
    result = generate_explanation(
        "TEST",
        "penny",
        72.0,
        "summary",
        {},
        quant_context=ctx,
    )
    assert result["source"] == "rules"
    assert "What would change my mind?" in result["text"]
    assert DISCLAIMER_FOOTER.split(".")[0] in result["text"]
    assert result["reasoning"]["system_rating"]["system_label"] == "buy"
