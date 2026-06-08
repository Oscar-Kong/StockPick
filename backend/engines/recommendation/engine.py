"""Final recommendation engine — layered scores + data confidence gate."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import DATA_CONFIDENCE_STRONG_BUY_MIN, DATA_CONFIDENCE_STRONG_REC_MIN
from engines.data_confidence import DataConfidence, build_data_confidence
from engines.feedback.predictions import expected_return_from_score, horizon_days_for_sleeve
from engines.scoring.pillars import PillarScores, compute_pillar_scores


@dataclass
class Recommendation:
    label: str
    confidence: float
    time_horizon_days: int
    expected_return_pct: float
    expected_downside_pct: float
    pillars: PillarScores
    data_confidence: DataConfidence
    gates: list[str] = field(default_factory=list)
    bull_case: str = ""
    bear_case: str = ""
    similar_signal: dict[str, Any] | None = None
    portfolio_impact: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation": self.label,
            "confidence": round(self.confidence, 1),
            "time_horizon_days": self.time_horizon_days,
            "expected_return_pct": self.expected_return_pct,
            "expected_downside_pct": self.expected_downside_pct,
            "pillars": self.pillars.to_dict(),
            "data_confidence": self.data_confidence.to_dict(),
            "gates": self.gates,
            "bull_case": self.bull_case,
            "bear_case": self.bear_case,
            "similar_signal": self.similar_signal,
            "portfolio_impact": self.portfolio_impact,
        }


def _base_label(final_score: float) -> str:
    if final_score >= 80:
        return "strong_buy"
    if final_score >= 65:
        return "buy"
    if final_score >= 50:
        return "watch"
    if final_score >= 35:
        return "hold"
    return "avoid"


def build_recommendation(
    *,
    symbol: str,
    sleeve: str,
    final_score: float,
    factors: list[dict[str, Any]],
    risk_score: float,
    risk_deduction: float,
    data_confidence: DataConfidence,
    valuation_score: float | None = None,
    catalyst_score: float | None = None,
    liquidity_penalty: float = 0.0,
    valuation_verdict: str | None = None,
    similar_signal: dict[str, Any] | None = None,
    portfolio_impact: dict[str, Any] | None = None,
    summary: str = "",
) -> Recommendation:
    pillars = compute_pillar_scores(
        factors,
        valuation_score=valuation_score,
        catalyst_score=catalyst_score,
        data_confidence=data_confidence.score,
        liquidity_penalty=liquidity_penalty,
        risk_deduction=risk_deduction,
    )

    label = _base_label(pillars.final_recommendation_score)
    gates: list[str] = []
    confidence = pillars.final_recommendation_score

    if data_confidence.score < DATA_CONFIDENCE_STRONG_REC_MIN:
        if label in ("strong_buy", "buy"):
            label = "watch"
            gates.append(f"Data confidence {data_confidence.score:.0f} < {DATA_CONFIDENCE_STRONG_REC_MIN}: no strong recommendation")

    if label == "strong_buy":
        if data_confidence.score < DATA_CONFIDENCE_STRONG_BUY_MIN:
            label = "buy"
            gates.append(f"Strong Buy requires data confidence >= {DATA_CONFIDENCE_STRONG_BUY_MIN}")
        if pillars.alpha_score < 75:
            label = "buy"
            gates.append("Strong Buy requires alpha score > 75")
        if valuation_verdict in ("expensive", "extremely_expensive"):
            label = "buy"
            gates.append("Valuation too negative for Strong Buy")
        if risk_score > 70:
            label = "watch"
            gates.append("Risk score too high for Strong Buy")
        if similar_signal and similar_signal.get("win_rate", 0.5) < 0.5:
            label = "buy"
            gates.append("Similar-signal backtest not positive")

    if data_confidence.score < 50:
        label = "high_risk_no_decision"
        confidence = min(confidence, 40.0)
        gates.append("Insufficient data confidence for any decision")

    horizon = horizon_days_for_sleeve(sleeve)
    exp_ret = expected_return_from_score(final_score, sleeve)
    exp_down = round(abs(exp_ret) * 0.7 + risk_deduction * 0.5, 2)

    bull = summary or f"{symbol}: alpha {pillars.alpha_score:.0f}, catalyst {pillars.catalyst_score:.0f} support upside."
    bear_parts = []
    if valuation_verdict in ("expensive", "extremely_expensive"):
        bear_parts.append("valuation extended")
    if risk_score > 60:
        bear_parts.append("elevated risk profile")
    if data_confidence.issues:
        bear_parts.append(data_confidence.issues[0])
    bear = "; ".join(bear_parts) or "Macro or sector rotation could invalidate setup."

    return Recommendation(
        label=label,
        confidence=confidence,
        time_horizon_days=horizon,
        expected_return_pct=exp_ret,
        expected_downside_pct=exp_down,
        pillars=pillars,
        data_confidence=data_confidence,
        gates=gates,
        bull_case=bull,
        bear_case=bear,
        similar_signal=similar_signal,
        portfolio_impact=portfolio_impact,
    )


def recommendation_from_context(
    symbol: str,
    sleeve: str,
    final_score: float,
    factors: list[dict[str, Any]],
    risk_assess: Any,
    info: dict[str, Any],
    *,
    reconcile: Any | None = None,
    valuation: Any | None = None,
    catalyst_score: float | None = None,
    liquidity_penalty: float = 0.0,
    similar_signal: dict[str, Any] | None = None,
    portfolio_impact: dict[str, Any] | None = None,
    summary: str = "",
) -> Recommendation:
    dc = build_data_confidence(symbol, reconcile)
    val_score = getattr(valuation, "valuation_score", None) if valuation else None
    val_verdict = getattr(valuation, "verdict", None) if valuation else None
    return build_recommendation(
        symbol=symbol,
        sleeve=sleeve,
        final_score=final_score,
        factors=factors,
        risk_score=float(getattr(risk_assess, "risk_score", 50)),
        risk_deduction=float(getattr(risk_assess, "deduction_pts", 0)),
        data_confidence=dc,
        valuation_score=val_score,
        catalyst_score=catalyst_score,
        liquidity_penalty=liquidity_penalty,
        valuation_verdict=val_verdict,
        similar_signal=similar_signal,
        portfolio_impact=portfolio_impact,
        summary=summary,
    )
