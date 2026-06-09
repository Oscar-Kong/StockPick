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


class VolatilityRiskV2(BaseModel):
    sufficient_data: bool = False
    observations: int = 0
    realized_volatility: float | None = None
    ewma_volatility: float | None = None
    downside_volatility: float | None = None
    historical_var: float | None = Field(default=None, description="Alpha-quantile return (loss if negative)")
    historical_es: float | None = Field(default=None, description="Expected shortfall in left tail")
    volatility_regime: str = "unknown"
    tail_risk: bool = False
    risk_penalty_pts: float = 0.0
    window: int = 21
    alpha: float = 0.05


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
    volatility: VolatilityRiskV2 | None = None


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


class WalkForwardResearchRequest(BaseModel):
    sleeve: str = Field(description="Strategy sleeve: penny | medium | compounder")
    start_date: str = Field(description="ISO date YYYY-MM-DD")
    end_date: str = Field(description="ISO date YYYY-MM-DD")
    rebalance_frequency: str = Field(default="monthly", description="weekly | monthly | quarterly | N sessions")
    forward_horizons: list[int] = Field(default_factory=lambda: [20])
    max_symbols: int = Field(default=30, ge=5, le=200)
    persist_snapshots: bool = True


class WalkForwardResearchResponse(BaseModel):
    run_id: str
    status: str
    sleeve: str
    start_date: str
    end_date: str
    rebalance_frequency: str
    forward_horizons: list[int]
    rebalance_periods: int
    periods_scored: int
    snapshots_written: int
    mean_turnover: float | None = None
    aggregate_horizons: dict[str, Any] = Field(default_factory=dict)
    periods: list[dict[str, Any]] = Field(default_factory=list)
    strategy_version: str = ""
    factor_model_version: str = ""
    weights_updated: bool = False


class WalkForwardRunDetailResponse(BaseModel):
    run_id: str
    run_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None


class PairsResearchRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, min_length=2)
    lookback_period: str = Field(default="1y", pattern="^(6mo|1y|2y|3y|5y)$")
    zscore_window: int = Field(default=60, ge=10, le=252)
    max_pairs: int | None = Field(default=100, ge=1, le=500)
    p_value_threshold: float | None = Field(default=None, ge=0, le=1)


class PairResearchItem(BaseModel):
    pair: list[str]
    symbol_y: str
    symbol_x: str
    hedge_ratio: float | None = None
    intercept: float | None = None
    p_value: float | None = None
    cointegrated_5pct: bool = False
    half_life_sessions: float | None = None
    mean_reverting: bool | None = None
    latest_z_score: float | None = None
    zscore_window: int | None = None
    spread_mean: float | None = None
    spread_std: float | None = None
    observations: int = 0
    sufficient: bool = False
    engine: str | None = None
    warning: str | None = None


class PairsResearchResponse(BaseModel):
    research_only: bool = True
    lookback_period: str
    symbols_requested: list[str] = []
    symbols_used: list[str] = []
    excluded: list[str] = []
    observation_count: int = 0
    pairs_evaluated: int = 0
    pairs_returned: int = 0
    cointegrated_count: int = 0
    insufficient_count: int = 0
    statsmodels_available: bool = False
    pairs: list[PairResearchItem] = []
    notes: list[str] = []


class QuantLabMainMetric(BaseModel):
    label: str
    value: str


class QuantLabLastRunSummary(BaseModel):
    """Read-only summary of latest persisted evidence for Quant Lab cards."""

    id: str
    available: bool
    reason: str | None = None
    generated_at: str | None = None
    run_id: str | None = None
    sleeve: str | None = None
    status: str | None = None
    sample_size: int | None = None
    main_metric: QuantLabMainMetric | None = None
    stale: bool = False
    stale_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    trust_indicator: str = "no_saved_run"
    research_only: bool = False
    tab: str | None = None


class QuantLabEvidenceResponse(BaseModel):
    sleeve: str
    generated_at: str
    validation_copy: str = (
        "Quant Lab validates the scoring system. It does not automatically change scan rankings."
    )
    factor_ic: QuantLabLastRunSummary
    walk_forward: QuantLabLastRunSummary
    predictions: QuantLabLastRunSummary
    pairs: QuantLabLastRunSummary
    jobs: QuantLabLastRunSummary
