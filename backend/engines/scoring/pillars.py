"""Layered scoring pillars — alpha, valuation, catalyst, penalties."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MOMENTUM_FACTORS = {
    "rs_vs_spy", "trend_quality", "breakout_strength", "rel_volume", "volume_surge",
    "sector_rs", "obv_slope", "capital_flow", "institutional_buy",
}
QUALITY_FACTORS = {
    "roic", "debt_ratio", "goodwill_ratio", "gross_operating_margin", "fcf_yield",
    "chip_concentration",
}
VALUE_FACTORS = {"pe_pct_5y", "pb_pct_5y", "ps_pct_5y", "fcf_yield"}
GROWTH_FACTORS = {"rev_growth", "eps_growth", "earnings_revision", "dividend_growth"}
SENTIMENT_FACTORS = {"social_sentiment", "sentiment_pos", "sentiment_neg"}
RISK_FACTORS = {"intraday_vol", "float_size"}


def _factor_suffix(factor_id: str) -> str:
    parts = factor_id.split("_", 1)
    return parts[1] if len(parts) > 1 else factor_id


def _bucket_score(factors: list[dict[str, Any]], bucket: set[str]) -> float | None:
    vals: list[float] = []
    for f in factors:
        fid = str(f.get("factor_id") or "")
        suffix = _factor_suffix(fid)
        if suffix not in bucket and fid not in bucket:
            continue
        ns = f.get("norm_score")
        if ns is not None:
            vals.append(float(ns))
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


@dataclass
class PillarScores:
    alpha_score: float
    valuation_score: float
    catalyst_score: float
    momentum: float | None = None
    quality: float | None = None
    growth: float | None = None
    value: float | None = None
    sentiment: float | None = None
    risk_factor: float | None = None
    data_quality_penalty: float = 0.0
    liquidity_penalty: float = 0.0
    risk_penalty: float = 0.0
    final_recommendation_score: float = 0.0
    factor_contributions: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha_score": self.alpha_score,
            "valuation_score": self.valuation_score,
            "catalyst_score": self.catalyst_score,
            "momentum": self.momentum,
            "quality": self.quality,
            "growth": self.growth,
            "value": self.value,
            "sentiment": self.sentiment,
            "risk_factor": self.risk_factor,
            "data_quality_penalty": self.data_quality_penalty,
            "liquidity_penalty": self.liquidity_penalty,
            "risk_penalty": self.risk_penalty,
            "final_recommendation_score": self.final_recommendation_score,
            "factor_contributions": self.factor_contributions,
        }


def compute_pillar_scores(
    factors: list[dict[str, Any]],
    *,
    valuation_score: float | None = None,
    catalyst_score: float | None = None,
    data_confidence: float | None = None,
    liquidity_penalty: float = 0.0,
    risk_deduction: float = 0.0,
) -> PillarScores:
    momentum = _bucket_score(factors, MOMENTUM_FACTORS)
    quality = _bucket_score(factors, QUALITY_FACTORS)
    growth = _bucket_score(factors, GROWTH_FACTORS)
    value = _bucket_score(factors, VALUE_FACTORS)
    sentiment = _bucket_score(factors, SENTIMENT_FACTORS)
    risk_factor = _bucket_score(factors, RISK_FACTORS)

    alpha_parts = [x for x in (momentum, quality, growth, sentiment) if x is not None]
    alpha = round(sum(alpha_parts) / len(alpha_parts), 2) if alpha_parts else 50.0

    val = valuation_score if valuation_score is not None else (value if value is not None else 50.0)
    cat = catalyst_score if catalyst_score is not None else (growth if growth is not None else 50.0)

    dq_penalty = 0.0
    if data_confidence is not None and data_confidence < 70:
        dq_penalty = round((70 - data_confidence) * 0.3, 2)

    risk_pen = round(float(risk_deduction), 2)
    liq_pen = round(float(liquidity_penalty), 2)

    final = round(
        max(
            0.0,
            min(
                100.0,
                alpha * 0.45 + val * 0.25 + cat * 0.20 - risk_pen - dq_penalty - liq_pen,
            ),
        ),
        2,
    )

    contributions: dict[str, float] = {}
    for f in factors:
        fid = str(f.get("factor_id") or "")
        contrib = f.get("contribution")
        if fid and contrib is not None:
            contributions[fid] = round(float(contrib), 2)

    return PillarScores(
        alpha_score=alpha,
        valuation_score=round(val, 2),
        catalyst_score=round(cat, 2),
        momentum=momentum,
        quality=quality,
        growth=growth,
        value=value,
        sentiment=sentiment,
        risk_factor=risk_factor,
        data_quality_penalty=dq_penalty,
        liquidity_penalty=liq_pen,
        risk_penalty=risk_pen,
        final_recommendation_score=final,
        factor_contributions=contributions,
    )
