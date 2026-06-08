"""Pydantic schemas for quant v2 API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FactorContributionV2(BaseModel):
    factor_id: str
    display_name: str
    norm_score: float
    weight: float
    contribution: float
    description: str = ""


class ScoreAttributionV2(BaseModel):
    raw_score: float
    regime_mult: float
    sector_tilt: float
    dq_multiplier: float
    openbb_delta: float = 0.0
    score_after_regime: float
    score_after_dq: float
    risk_deduction: float
    final_score: float


class RiskBreakdownV2(BaseModel):
    risk_score: float = Field(ge=0, le=100)
    deduction_pts: float = Field(ge=0)
    items: list[dict[str, Any]] = []


class MarketRegimeV2(BaseModel):
    regime: str
    as_of_date: str
    features: dict[str, Any] = {}


class SleeveWeightsV2(BaseModel):
    sleeve: str
    regime: str
    dynamic_enabled: bool
    weights: dict[str, float]
    weights_by_regime: dict[str, dict[str, float]] | None = None


class V2ScoreResponse(BaseModel):
    symbol: str
    sleeve: str
    score: float = Field(ge=0, le=100)
    market_regime: str | None = None
    dynamic_weights: bool = False
    risk_level: str
    summary: str
    factors: list[FactorContributionV2]
    attribution: ScoreAttributionV2
    risk: RiskBreakdownV2
    alerts: list[dict[str, str]] = []
    strategy_version: str
    factor_model_version: str
    parity_delta: float | None = Field(
        default=None,
        description="Absolute delta vs legacy analyze_symbol score (debug/validation)",
    )
    metrics: dict[str, Any] = {}
    position_sizing: "PositionSizingV2 | None" = None
    recommendation: "RecommendationV2 | None" = None
    valuation: "ValuationV2 | None" = None
    earnings_setup: dict[str, Any] = {}
    similar_signal: "SimilarSignalV2 | None" = None
    portfolio_impact: "PortfolioImpactV2 | None" = None
    prediction_snapshot_id: int | None = None
    agents: dict[str, Any] | None = None


class UnifiedRiskV2(BaseModel):
    symbol: str
    sleeve: str
    risk_index: float = Field(ge=0, le=100, description="0=low danger, 100=high danger")
    safety_score: float = Field(ge=0, le=100, description="100=low danger")
    deduction_pts: float = Field(ge=0)
    macro: list[str] = []
    company: list[str] = []
    events: list[str] = []
    score_deductions: list[dict[str, Any]] = []
    alerts: list[dict[str, str]] = []
    breakdown: list[dict[str, Any]] = []


class PositionSizingV2(BaseModel):
    symbol: str
    sleeve: str
    recommended_weight_pct: float = Field(ge=0, le=100)
    max_weight_pct: float = Field(ge=0, le=100)
    stop_loss_pct: float = Field(ge=0)
    portfolio_allocation_pct: float = Field(ge=0, le=100)
    conviction: float = Field(ge=0, le=100)
    sleeve_max_pct: float = Field(ge=0, le=100)
    risk_multiplier: float = Field(ge=0, le=1)
    dq_multiplier: float = Field(ge=0, le=1.5)
    rationale: str = ""


class DataConfidenceV2(BaseModel):
    data_confidence: float = Field(ge=0, le=100)
    issues: list[str] = []
    strengths: list[str] = []
    strong_recommendation_allowed: bool = True
    strong_buy_allowed: bool = True


class PillarScoresV2(BaseModel):
    alpha_score: float
    valuation_score: float
    catalyst_score: float
    momentum: float | None = None
    quality: float | None = None
    growth: float | None = None
    value: float | None = None
    sentiment: float | None = None
    data_quality_penalty: float = 0.0
    liquidity_penalty: float = 0.0
    risk_penalty: float = 0.0
    final_recommendation_score: float = 0.0
    factor_contributions: dict[str, float] = {}


class ValuationV2(BaseModel):
    dcf_fair_value: float | None = None
    dcf_bull: float | None = None
    dcf_bear: float | None = None
    peer_fair_value: float | None = None
    reverse_dcf_implied_growth_pct: float | None = None
    margin_of_safety_pct: float | None = None
    premium_to_peers_pct: float | None = None
    valuation_score: float = 50.0
    verdict: str = "fair"
    assumptions: dict[str, Any] = Field(default_factory=dict)
    sensitivity_grid: dict[str, Any] = Field(default_factory=dict)


class RecommendationV2(BaseModel):
    recommendation: str
    confidence: float = Field(ge=0, le=100)
    time_horizon_days: int
    expected_return_pct: float
    expected_downside_pct: float
    pillars: PillarScoresV2
    data_confidence: DataConfidenceV2
    gates: list[str] = []
    bull_case: str = ""
    bear_case: str = ""


class SimilarSignalV2(BaseModel):
    sample_n: int = 0
    avg_forward_return_pct: float | None = None
    win_rate: float | None = None
    max_drawdown_pct: float | None = None
    forward_days: int = 60


class PortfolioImpactV2(BaseModel):
    correlation_with_portfolio: float | None = None
    sector_exposure_after_pct: float | None = None
    portfolio_beta_impact: float | None = None
