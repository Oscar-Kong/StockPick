"""Independent stability and entry-risk assessment for penny candidates.

The public seam intentionally accepts only point-in-time OHLCV history and an
alpha score.  Callers do not need to know the factor transforms or gate rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

import pandas as pd

from scoring.metrics import clip100


@dataclass(frozen=True)
class StabilityAssessment:
    score: float
    classification: str
    hard_gates: tuple[str, ...]
    factors: dict[str, float]
    raw: dict[str, float]


@dataclass(frozen=True)
class EntryRiskAssessment:
    score: float
    classification: str
    reasons: tuple[str, ...]
    source: str = "daily_ohlcv_proxy"


@dataclass(frozen=True)
class PennyCandidateDecision:
    alpha_score: float
    stability: StabilityAssessment
    entry: EntryRiskAssessment
    decision_state: str

    def to_metrics_dict(self) -> dict[str, object]:
        return {
            "alpha_score": self.alpha_score,
            "stability_score": self.stability.score,
            "stability_classification": self.stability.classification,
            "stability_hard_gates": list(self.stability.hard_gates),
            "stability_factors": dict(self.stability.factors),
            "stability_raw": dict(self.stability.raw),
            "entry_risk_score": self.entry.score,
            "entry_risk_classification": self.entry.classification,
            "entry_risk_reasons": list(self.entry.reasons),
            "entry_risk_source": self.entry.source,
            "decision_state": self.decision_state,
        }


def _inverse_score(value: float, good: float, bad: float) -> float:
    return 100.0 - clip100(value, good, bad)


def _classification(score: float, gates: tuple[str, ...]) -> str:
    if gates or score < 50:
        return "rejected"
    if score < 65:
        return "high_risk"
    if score < 80:
        return "normal"
    return "stable"


def _entry_classification(score: float) -> str:
    if score >= 80:
        return "no_chase"
    if score >= 60:
        return "extended"
    if score >= 40:
        return "wait"
    if score >= 20:
        return "acceptable"
    return "normal"


def _rejected_decision(alpha: float, reason: str) -> PennyCandidateDecision:
    stability = StabilityAssessment(
        score=0.0,
        classification="rejected",
        hard_gates=(reason,),
        factors={},
        raw={},
    )
    entry = EntryRiskAssessment(100.0, "no_chase", (reason,))
    return PennyCandidateDecision(alpha, stability, entry, "no_trade")


def assess_penny_stability(
    history: pd.DataFrame | None,
    *,
    alpha_score: float,
) -> PennyCandidateDecision:
    """Assess tradability without blending the result into alpha ranking."""
    alpha = round(max(0.0, min(100.0, float(alpha_score))), 1)
    if history is None or len(history) < 21:
        return _rejected_decision(alpha, "insufficient_history")

    frame = history.iloc[-21:].copy()
    required = ("open", "high", "low", "close", "volume")
    if any(column not in frame.columns for column in required):
        return _rejected_decision(alpha, "invalid_history")
    numeric = frame.loc[:, required].apply(pd.to_numeric, errors="coerce")
    finite = numeric.map(lambda value: isfinite(float(value))).all().all()
    valid_prices = (numeric.loc[:, ("open", "high", "low", "close")] > 0).all().all()
    valid_volume = (numeric["volume"] >= 0).all()
    if not finite or not valid_prices or not valid_volume:
        return _rejected_decision(alpha, "invalid_history")
    frame.loc[:, required] = numeric
    close = frame["close"].astype(float)
    volume = frame["volume"].astype(float)
    completed_close = close.iloc[:-1]
    completed_volume = volume.iloc[:-1]
    dollar_volume = completed_close * completed_volume
    returns = completed_close.pct_change().dropna()

    median_dollar_volume = float(dollar_volume.median())
    abs_returns = returns.abs()
    aligned_dollar_volume = dollar_volume.iloc[1:]
    valid_dollar_volume = aligned_dollar_volume[aligned_dollar_volume > 0]
    amihud_observations = (abs_returns / valid_dollar_volume).dropna()
    # Missing/zero liquidity receives the bad-end transform while remaining
    # JSON-safe; the hard gate carries the user-facing rejection reason.
    amihud = (
        float(amihud_observations.mean())
        if not amihud_observations.empty
        else 250.0 / (1_000_000 * 10_000)
    )
    price_impact_bps_per_million = amihud * 1_000_000 * 10_000

    negative_returns = returns[returns < 0]
    downside_volatility = (
        float(negative_returns.std(ddof=0) * sqrt(252) * 100)
        if len(negative_returns)
        else 0.0
    )
    previous_close = close.shift(1)
    signed_gaps = ((frame["open"].astype(float) / previous_close) - 1.0).dropna() * 100
    gaps = signed_gaps.abs()
    median_abs_gap = float(gaps.iloc[:-1].median()) if len(gaps) > 1 else 0.0

    path = float(completed_close.diff().abs().sum())
    trend_efficiency = (
        abs(float(completed_close.iloc[-1] - completed_close.iloc[0])) / path
        if path > 0
        else 0.0
    )
    volume_consistency = (
        float(dollar_volume.quantile(0.25) / median_dollar_volume)
        if median_dollar_volume > 0
        else 0.0
    )
    range_proxy_pct = float(
        ((frame["high"].iloc[-1] - frame["low"].iloc[-1]) / close.iloc[-1]) * 100
    )

    factors = {
        "dollar_liquidity": clip100(median_dollar_volume, 250_000, 5_000_000),
        "amihud_quality": _inverse_score(price_impact_bps_per_million, 5, 250),
        "spread_proxy_quality": _inverse_score(range_proxy_pct, 2, 15),
        "downside_risk_quality": _inverse_score(downside_volatility, 20, 120),
        "gap_stability": _inverse_score(median_abs_gap, 1, 8),
        "trend_efficiency": max(0.0, min(100.0, trend_efficiency * 100)),
        "volume_consistency": max(0.0, min(100.0, volume_consistency * 100)),
    }
    stability_score = round(
        factors["dollar_liquidity"] * 0.25
        + factors["amihud_quality"] * 0.20
        + factors["spread_proxy_quality"] * 0.15
        + factors["downside_risk_quality"] * 0.15
        + factors["gap_stability"] * 0.15
        + factors["trend_efficiency"] * 0.10,
        1,
    )
    gates: list[str] = []
    if median_dollar_volume < 250_000:
        gates.append("insufficient_dollar_liquidity")
    hard_gates = tuple(gates)
    raw = {
        "median_dollar_volume_20d": round(median_dollar_volume, 2),
        "amihud_20d": amihud,
        "price_impact_bps_per_million": round(price_impact_bps_per_million, 2),
        "downside_volatility_annualized_pct": round(downside_volatility, 2),
        "median_abs_gap_pct": round(median_abs_gap, 2),
        "trend_efficiency_20d": round(trend_efficiency, 4),
        "volume_consistency_20d": round(volume_consistency, 4),
        "range_proxy_pct": round(range_proxy_pct, 2),
    }
    stability = StabilityAssessment(
        score=stability_score,
        classification=_classification(stability_score, hard_gates),
        hard_gates=hard_gates,
        factors={key: round(value, 1) for key, value in factors.items()},
        raw=raw,
    )

    latest_gap = float(signed_gaps.iloc[-1]) if len(signed_gaps) else 0.0
    positive_gap_risk = clip100(max(0.0, latest_gap), 2, 10)
    extension_risk = clip100(range_proxy_pct, 4, 15)
    entry_score = round(positive_gap_risk * 0.70 + extension_risk * 0.30, 1)
    reasons: list[str] = []
    if latest_gap >= 10:
        reasons.append("extreme_latest_gap")
    elif latest_gap >= 4:
        reasons.append("elevated_latest_gap")
    elif latest_gap <= -8:
        reasons.append("large_gap_down")
        entry_score = max(entry_score, 50.0)
    if range_proxy_pct >= 10:
        reasons.append("wide_daily_range_proxy")
    entry_classification = "no_chase" if latest_gap >= 10 else _entry_classification(entry_score)
    entry = EntryRiskAssessment(
        score=entry_score,
        classification=entry_classification,
        reasons=tuple(reasons),
    )

    decision_state = "no_trade" if stability.classification == "rejected" else "watch"
    return PennyCandidateDecision(alpha, stability, entry, decision_state)
