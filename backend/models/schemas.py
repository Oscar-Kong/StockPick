"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Bucket(str, Enum):
    penny = "penny"
    medium = "medium"
    compounder = "compounder"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ScanStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class Signal(BaseModel):
    name: str
    value: float
    weight: float
    contribution: float
    description: str = ""


class StockResult(BaseModel):
    symbol: str
    price: float
    score: float = Field(ge=0, le=100)
    signals: list[Signal] = []
    risk_level: RiskLevel = RiskLevel.medium
    summary: str = ""
    bucket: Bucket
    metrics: dict[str, Any] = {}
    valuation_warnings: list[str] = []
    earnings_date: str | None = None
    days_until_earnings: int | None = None
    earnings_soon: bool = False


class ScanJobResponse(BaseModel):
    job_id: str
    bucket: Bucket
    status: ScanStatus


class ScanStatusResponse(BaseModel):
    job_id: str
    bucket: Bucket
    status: ScanStatus
    progress: float = Field(ge=0, le=100)
    message: str = ""
    results: list[StockResult] = []
    completed_at: datetime | None = None
    parity_summary: dict[str, Any] | None = None
    scoring_engine_used: bool | None = None


class ScanOptions(BaseModel):
    max_results: int = 25
    min_price: float | None = None
    max_price: float | None = None
    min_volume: float | None = None
    exclude_sectors: list[str] = []


class ScanPickSummaryRequest(BaseModel):
    score: float = Field(ge=0, le=100)
    summary: str = ""
    signals: list[Signal] = []
    metrics: dict[str, Any] = {}
    locale: str = "en"


class ScanPickSummaryResponse(BaseModel):
    symbol: str
    bucket: Bucket
    background: str
    why_picked: str
    text: str
    source: str = "rules"


class OHLCPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class StockDetail(BaseModel):
    symbol: str
    price: float
    ohlc: list[OHLCPoint] = []
    fundamentals: dict[str, Any] = {}
    scores: dict[str, float] = {}
    explanation: str = ""
    ai_explanation: str = ""
    bucket: Bucket | None = None
    earnings_date: str | None = None
    days_until_earnings: int | None = None
    earnings_soon: bool = False
    valuation_warnings: list[str] = []
    news_headlines: list[str] = []
    news_categories: dict[str, int] = {}
    backtest: dict[str, Any] | None = None
    data_quality_score: float | None = None
    strategy_version: str | None = None


class LatestScanResponse(BaseModel):
    bucket: Bucket
    results: list[StockResult] = []
    completed_at: datetime | None = None
    strategy_version: str | None = None
    parity_summary: dict[str, Any] | None = None
    scoring_engine_used: bool | None = None


class SavedScanCreateRequest(BaseModel):
    name: str | None = None
    bucket: Bucket
    options: dict[str, Any] = {}
    results: list[StockResult] = []
    strategy_version: str | None = None
    completed_at: datetime | None = None


class SavedScanItem(BaseModel):
    id: int
    name: str
    bucket: Bucket
    options: dict[str, Any] = {}
    results: list[StockResult] = []
    result_count: int = 0
    strategy_version: str | None = None
    completed_at: datetime | None = None
    created_at: datetime


class SavedReportCreateRequest(BaseModel):
    symbol: str
    bucket: Bucket | None = None
    title: str | None = None
    notes: str = ""
    report: dict[str, Any] = {}


class SavedReportUpdateRequest(BaseModel):
    title: str | None = None
    notes: str | None = None
    report: dict[str, Any] | None = None


class SavedReportItem(BaseModel):
    id: int
    symbol: str
    bucket: Bucket | None = None
    title: str
    notes: str = ""
    report: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class SavedAnalyzeItem(BaseModel):
    id: int
    symbol: str
    bucket: Bucket
    payload: dict[str, Any] = {}
    score: float | None = None
    data_quality_score: float | None = None
    created_at: datetime
    updated_at: datetime


class SavedProgressSummary(BaseModel):
    scan_count: int = 0
    report_count: int = 0
    analyze_count: int = 0
    trade_count: int = 0
    latest_scan_bucket: Bucket | None = None
    latest_scan_at: datetime | None = None
    latest_report_symbol: str | None = None
    latest_report_at: datetime | None = None
    latest_analyze_symbol: str | None = None
    latest_analyze_bucket: Bucket | None = None
    latest_analyze_at: datetime | None = None
    latest_trade_symbol: str | None = None
    latest_trade_at: datetime | None = None


class TraderIntelSource(BaseModel):
    title: str
    url: str
    source_type: str


class TraderKnownObservation(BaseModel):
    observation: str
    confidence: str


class TraderIntegrationRecipe(BaseModel):
    style: str
    bucket_bias: list[str] = []
    scan_tilt: dict[str, Any] = {}
    risk_controls: list[str] = []


class TraderProfileItem(BaseModel):
    slug: str
    name: str
    aliases: list[str] = []
    profile_type: str
    data_reliability: str
    summary: str
    strategy_principles: list[str] = []
    known_observations: list[TraderKnownObservation] = []
    integration_recipe: TraderIntegrationRecipe
    sources: list[TraderIntelSource] = []


class TraderProfileListResponse(BaseModel):
    collected_at_utc: str
    notes: list[str] = []
    profiles: list[TraderProfileItem] = []


class TraderPresetResponse(BaseModel):
    slug: str
    bucket: Bucket
    scan_options: dict[str, Any] = {}
    backtest_overrides: dict[str, Any] = {}
    horizon: str | None = None
    notes: list[str] = []


class TraderBacktestVariantResult(BaseModel):
    hold_days: int
    stop_pct: float
    target_pct: float | None = None
    total_return_pct: float = 0
    sharpe_ratio: float = 0
    max_drawdown_pct: float = 0
    win_rate_pct: float = 0
    trade_count: int = 0
    annualized_return_pct: float | None = None
    validation_passed: bool | None = None
    backtest_engine: str = "default"


class TraderQuickCompareResponse(BaseModel):
    slug: str
    bucket: Bucket
    symbol: str
    horizon: str
    baseline: TraderBacktestVariantResult
    trader_style: TraderBacktestVariantResult
    delta_total_return_pct: float = 0
    delta_sharpe_ratio: float = 0
    notes: list[str] = []


class TradeCreateRequest(BaseModel):
    symbol: str
    sleeve: str | None = Field(
        default=None,
        description="penny | medium | compounder; inferred from tags/watchlist if omitted",
    )
    side: str = "long"
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: float
    exit_price: float | None = None
    quantity: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    setup_tags: list[str] = []
    thesis: str = ""
    notes: str = ""


class TradeUpdateRequest(BaseModel):
    exit_time: datetime | None = None
    exit_price: float | None = None
    quantity: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    setup_tags: list[str] | None = None
    thesis: str | None = None
    notes: str | None = None


class TradeReviewSnapshot(BaseModel):
    pnl_abs: float | None = None
    pnl_pct: float | None = None
    planned_rr: float | None = None
    quality_score: float = 0
    quality_label: str = "D"
    process_good: bool = False
    review_note: str = ""
    flags: list[str] = []
    image_insight: str = ""
    image_tags: list[str] = []
    image_analysis_status: str = "not_run"


class TradeItem(BaseModel):
    id: int
    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: float
    exit_price: float | None = None
    quantity: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    setup_tags: list[str] = []
    thesis: str = ""
    notes: str = ""
    screenshot_path: str | None = None
    review: TradeReviewSnapshot = TradeReviewSnapshot()
    created_at: datetime
    updated_at: datetime


class TradeStatsResponse(BaseModel):
    total_trades: int = 0
    closed_trades: int = 0
    win_rate_pct: float = 0
    avg_pnl_pct: float = 0
    avg_quality_score: float = 0
    strong_process_rate_pct: float = 0
    profitable_but_weak_count: int = 0
    disciplined_loss_count: int = 0
    top_flags: list[dict[str, Any]] = []


class WatchlistRefreshResponse(BaseModel):
    refreshed: int
    failed: int
    results: list[dict[str, Any]] = []


class WatchlistItem(BaseModel):
    symbol: str
    bucket: Bucket
    notes: str = ""
    added_at: datetime
    price: float | None = None
    score: float | None = None
    summary: str = ""
    last_scanned_at: datetime | None = None
    earnings_date: str | None = None
    days_until_earnings: float | None = None
    valuation_warnings: list[str] = []


class WatchlistCreate(BaseModel):
    symbol: str
    bucket: Bucket
    notes: str = ""


class WatchlistNotesUpdate(BaseModel):
    notes: str = ""


class WatchlistImportRequest(BaseModel):
    input: str = Field(..., description="Tickers separated by commas, spaces, or new lines")
    bucket: Bucket | str = "auto"
    notes: str = ""


class WatchlistImportRow(BaseModel):
    symbol: str
    bucket: str
    price: float | None = None
    score: float | None = None
    summary: str = ""
    notes: str = ""
    added: bool
    error: str | None = None
    report: dict[str, Any] | None = None


class WatchlistImportResponse(BaseModel):
    results: list[WatchlistImportRow]
    added_count: int
    failed_count: int


class BacktestTearSheet(BaseModel):
    total_return_pct: float = 0
    annualized_return_pct: float | None = None
    buy_hold_return_pct: float = 0
    excess_return_vs_buy_hold_pct: float | None = None
    max_drawdown_pct: float = 0
    sharpe_ratio: float = 0
    calmar_ratio: float | None = None
    win_rate_pct: float = 0
    trade_count: int = 0
    avg_win_pct: float | None = None
    avg_loss_pct: float | None = None
    profit_factor: float | None = None
    validation_passed: bool | None = None
    in_sample_sharpe: float | None = None
    out_of_sample_sharpe: float | None = None
    entry_variant: str | None = None
    backtest_engine: str = "default"


class BacktestResult(BaseModel):
    initial_capital: float = 10000
    final_capital: float = 10000
    total_return_pct: float = 0
    annualized_return_pct: float | None = None
    buy_hold_return_pct: float = 0
    win_rate_pct: float = 0
    trade_count: int = 0
    max_drawdown_pct: float = 0
    sharpe_ratio: float = 0
    trades: list[dict[str, Any]] = []
    message: str = ""
    horizon: str | None = None
    strategy_version: str | None = None
    entry_variant: str | None = None
    tear_sheet: BacktestTearSheet | None = None
    validation_passed: bool | None = None
    validation_notes: list[str] = []
    in_sample: dict[str, Any] | None = None
    out_of_sample: dict[str, Any] | None = None
    backtest_engine: str = "default"


class BacktestSweepRequest(BaseModel):
    horizon: str | None = None
    entry_variant: str | None = None
    hold_days: list[int] = []
    stop_pct: list[float] = []
    target_pct: list[float | None] = []
    max_trials: int = Field(default=27, ge=1, le=200)
    top_k: int = Field(default=10, ge=1, le=50)


class BacktestSweepItem(BaseModel):
    hold_days: int
    stop_pct: float
    target_pct: float | None = None
    total_return_pct: float = 0
    annualized_return_pct: float | None = None
    sharpe_ratio: float = 0
    deflated_sharpe: float | None = None
    max_drawdown_pct: float = 0
    win_rate_pct: float = 0
    trade_count: int = 0
    validation_passed: bool | None = None
    validation_notes: list[str] = []
    backtest_engine: str = "default"


class BacktestSweepDiagnostics(BaseModel):
    n_trials: int = 0
    median_sharpe: float = 0
    median_return_pct: float = 0
    oos_validation_pass_rate: float = 0
    walk_forward_stable: bool = True
    overfit_risk: str = "low"
    oos_split_ratio: float = 0.7
    best_deflated_sharpe: float | None = None
    message: str = ""


class BacktestSweepResponse(BaseModel):
    symbol: str
    bucket: Bucket
    horizon: str
    engine: str = "default"
    entry_variant: str | None = None
    strategy_version: str | None = None
    trials: int = 0
    best: BacktestSweepItem | None = None
    results: list[BacktestSweepItem] = []
    sweep_diagnostics: BacktestSweepDiagnostics | None = None
    message: str = ""


class EntryVariantItem(BaseModel):
    id: str
    label: str


class EntryVariantListResponse(BaseModel):
    bucket: Bucket
    variants: list[EntryVariantItem] = []


class MultiHorizonBacktestResponse(BaseModel):
    horizons: dict[str, Any] = {}
    overall_passed: bool = False
    strategy_version: str = ""
    message: str = ""


class PortfolioOptimizeRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, min_length=2)
    objective: str = Field(
        default="max_sharpe",
        pattern="^(max_sharpe|min_vol|risk_parity|target_return|kelly)$",
    )
    kelly_overlay: bool = False
    max_weight: float = Field(default=0.30, gt=0, le=1)
    long_only: bool = True
    cash_buffer: float = Field(default=0.0, ge=0, lt=1)
    target_return: float | None = Field(default=None, ge=-1, le=2)
    lookback_period: str = Field(default="1y", pattern="^(6mo|1y|2y|3y|5y)$")


class PortfolioOptimizeItem(BaseModel):
    symbol: str
    weight: float
    annual_return: float | None = None
    annual_volatility: float | None = None


class PortfolioOptimizeResponse(BaseModel):
    objective: str
    optimizer: str
    symbols_requested: list[str] = []
    symbols_used: list[str] = []
    excluded: list[str] = []
    weights: list[PortfolioOptimizeItem] = []
    expected_return: float | None = None
    expected_volatility: float | None = None
    expected_sharpe: float | None = None
    constraints: dict[str, Any] = {}
    notes: list[str] = []


class PortfolioPolicyBacktestRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, min_length=2)
    policy: str = Field(default="equal_weight", pattern="^(equal_weight|inverse_vol|top_n_momentum)$")
    rebalance: str = Field(default="monthly", pattern="^(weekly|monthly)$")
    top_n: int = Field(default=5, ge=1, le=20)
    lookback_period: str = Field(default="1y", pattern="^(6mo|1y|2y|3y|5y)$")
    initial_capital: float = Field(default=10000.0, gt=0)
    max_weight: float = Field(default=0.35, gt=0, le=1)
    cash_buffer: float = Field(default=0.0, ge=0, lt=1)
    institutional: bool = False
    sleeve: str | None = Field(default="penny", pattern="^(penny|medium|compounder)$")
    fee_bps: float | None = Field(default=None, ge=0, le=100)
    slip_bps: float | None = Field(default=None, ge=0, le=100)
    use_universe_pit: bool = True


class PortfolioPolicyBacktestResponse(BaseModel):
    policy: str
    rebalance: str
    engine: str = "policy_sim"
    lookback_period: str
    symbols_requested: list[str] = []
    symbols_used: list[str] = []
    excluded: list[str] = []
    initial_capital: float
    final_capital: float
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    volatility_pct: float
    sharpe_ratio: float
    benchmark_return_pct: float = 0.0
    turnover_pct: float = 0.0
    rebalance_count: int = 0
    equity_curve: list[dict[str, Any]] = []
    weights_history: list[dict[str, Any]] = []
    notes: list[str] = []
    sortino_ratio: float | None = None
    calmar_ratio: float | None = None
    beta: float | None = None
    alpha_vs_spy_pct: float | None = None
    total_cost_pct: float | None = None
    total_cost_usd: float | None = None
    run_id: str | None = None
    cost_events: list[dict[str, Any]] = []
    institutional: bool = False


class FactorExposureRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, min_length=2)
    benchmark: str = Field(default="SPY", min_length=1, max_length=12)
    lookback_period: str = Field(default="1y", pattern="^(6mo|1y|2y|3y|5y)$")
    correlation_window: int = Field(default=60, ge=10, le=252)
    n_components: int | None = Field(default=None, ge=1, le=20)
    pc1_concentration_threshold: float = Field(default=0.45, gt=0, le=1)


class FactorExposureResponse(BaseModel):
    diagnostic_only: bool = True
    benchmark: str
    lookback_period: str
    symbols_requested: list[str] = []
    symbols_used: list[str] = []
    excluded: list[str] = []
    observation_count: int = 0
    betas: dict[str, dict[str, Any]] = {}
    correlation: dict[str, Any] = {}
    pca: dict[str, Any] = {}
    concentration_warning: bool = False
    notes: list[str] = []


class AlphaSignalItem(BaseModel):
    symbol: str
    alpha_score: float
    rank: int
    source: str = "rule_proxy"


class AlphaLatestResponse(BaseModel):
    bucket: Bucket
    as_of: str
    model_name: str
    model_version: str
    enabled: bool
    items: list[AlphaSignalItem] = []
    notes: list[str] = []


class AlphaIngestItem(BaseModel):
    symbol: str
    alpha_score: float
    rank: int | None = None


class AlphaIngestRequest(BaseModel):
    bucket: Bucket = Bucket.penny
    as_of: str | None = None
    model_version: str = "offline-v1"
    items: list[AlphaIngestItem] = []


class AlphaIngestResponse(BaseModel):
    ok: bool
    bucket: Bucket
    model_version: str
    ingested: int
    message: str = ""


class AllocationRecommendationItem(BaseModel):
    symbol: str
    target_weight: float
    score: float | None = None
    confidence: float | None = None


class AllocationRecommendationResponse(BaseModel):
    bucket: Bucket
    as_of: str
    model_name: str
    model_version: str
    enabled: bool
    source: str
    symbols_used: list[str] = []
    excluded: list[str] = []
    target_weights: list[AllocationRecommendationItem] = []
    constraints: dict[str, Any] = {}
    notes: list[str] = []


class LeanExportRequest(BaseModel):
    bucket: Bucket = Bucket.penny
    symbols: list[str] = []
    rebalance: str = Field(default="monthly", pattern="^(weekly|monthly)$")
    objective: str = Field(default="min_vol", pattern="^(max_sharpe|min_vol|target_return)$")
    lookback_period: str = Field(default="1y", pattern="^(6mo|1y|2y|3y|5y)$")
    max_weight: float = Field(default=0.30, gt=0, le=1)
    cash_buffer: float = Field(default=0.05, ge=0, lt=1)
    include_alpha: bool = True
    include_latest_scan: bool = True
    export_name: str | None = None
    notes: str = ""


class LeanExportResponse(BaseModel):
    export_id: str
    created_at: str
    bucket: Bucket
    symbols: list[str] = []
    strategy_version: str | None = None
    file_path: str
    payload: dict[str, Any] = {}
    message: str = ""


class LeanImportSummaryRequest(BaseModel):
    export_id: str
    status: str = "completed"
    metrics: dict[str, Any] = {}
    notes: str = ""


class LeanImportSummaryResponse(BaseModel):
    ok: bool
    export_id: str
    status: str
    summary_path: str
    message: str = ""


class ReconcileResponse(BaseModel):
    symbol: str
    canonical: dict[str, Any] = {}
    quality_score: float = 0
    source_audit: dict[str, str] = {}
    flags: list[str] = []
    fields: list[dict[str, Any]] = []


class DataQualityResponse(BaseModel):
    symbol: str
    quality_score: float = 0
    flags: list[dict[str, Any]] = []
    reconcile: dict[str, Any] = {}


class StrategyVersionResponse(BaseModel):
    version_id: str
    bucket: str
    config: dict[str, Any] = {}


class JobLogEntry(BaseModel):
    job_name: str
    status: str
    message: str = ""
    symbols_processed: int = 0
    errors: int = 0
    started_at: str | None = None
    finished_at: str | None = None


class SchedulerStatusResponse(BaseModel):
    enabled: bool = True
    recent_jobs: list[JobLogEntry] = []
    quandl_configured: bool = False


class ExplainRequest(BaseModel):
    symbol: str
    bucket: Bucket | None = None


class ExplainResponse(BaseModel):
    symbol: str
    explanation: str
    source: str = "rules"
    sections: dict[str, str] = {}
    reasoning: dict[str, Any] = {}


class OpenBBRiskResponse(BaseModel):
    symbol: str
    governance_score: float
    warnings: list[str] = []
    flags: list[str] = []
    insider_sell_ratio: float | None = None
    recent_filings: list[dict[str, Any]] = []
    openbb_available: bool = False


class HealthResponse(BaseModel):
    status: str
    alpha_vantage_configured: bool
    fred_configured: bool
    newsapi_configured: bool
    finnhub_configured: bool = False
    fmp_configured: bool = False
    llm_configured: bool = False
    quandl_configured: bool = False
    openbb_enabled: bool = False
    scheduler_enabled: bool = False
    app_env: str = "development"
    primary_price_source: str = "finnhub"
    primary_fundamentals_source: str = "fmp"
    primary_news_source: str = "finnhub"
    database_dialect: str = "sqlite"
    job_queue_backend: str = "sync"
    redis_connected: bool = False
    strategy_version: str = ""
    factor_model_version: str = ""


class ApiSettingItem(BaseModel):
    key: str
    label: str
    description: str = ""
    enabled: bool
    env_default: bool = False
    overridden: bool = False
    configured: bool | None = None
    requires_key: str | None = None


class ApiSettingsGroup(BaseModel):
    id: str
    title: str
    description: str = ""
    items: list[ApiSettingItem] = []


class ApiSettingsResponse(BaseModel):
    groups: list[ApiSettingsGroup] = []
    primary_price_source: str = "finnhub"
    primary_fundamentals_source: str = "fmp"
    primary_news_source: str = "finnhub"
    app_env: str = "development"


class ApiSettingsPatchRequest(BaseModel):
    updates: dict[str, bool]


class ApiSettingsResetRequest(BaseModel):
    keys: list[str] | None = None


class AnalyzeAlert(BaseModel):
    type: str
    severity: str
    message: str


class AnalyzeWatchlistRow(BaseModel):
    symbol: str
    bucket: str
    notes: str = ""
    price: float | None = None
    score: float | None = None
    summary: str = ""
    last_scanned_at: str | None = None
    stale: bool = False
    earnings_date: str | None = None
    days_until_earnings: float | None = None
    valuation_warnings: list[str] = []
    data_quality_score: float | None = None
    technicals: dict[str, Any] = {}
    alerts: list[AnalyzeAlert] = []
    alert_count: int = 0


class AnalyzeWatchlistResponse(BaseModel):
    rows: list[AnalyzeWatchlistRow]
    alert_total: int = 0


class AnalyzeSymbolResponse(BaseModel):
    symbol: str
    assigned_bucket: str
    price: float
    score: float
    risk_level: str
    summary: str = ""
    signals: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    valuation_warnings: list[str] = []
    earnings_date: str | None = None
    days_until_earnings: int | None = None
    earnings_soon: bool = False
    data_quality_score: float | None = None
    reconcile: dict[str, Any] = {}
    technicals: dict[str, Any] = {}
    bucket_fit: dict[str, Any] = {}
    alerts: list[AnalyzeAlert] = []
    ohlc: list[dict[str, Any]] = []
    fundamentals: dict[str, Any] = {}
    error: str | None = None


class AnalyzeCompareEntry(BaseModel):
    symbol: str
    assigned_bucket: str | None = None
    price: float | None = None
    score: float | None = None
    risk_level: str | None = None
    passed_hard_filter: bool | None = None
    summary: str | None = None
    reconcile_quality: float | None = None
    canonical: dict[str, Any] = {}
    technicals: dict[str, Any] = {}
    alert_count: int = 0
    stale: bool = False
    valuation_warnings: list[str] = []
    on_watchlist: bool = False
    error: str | None = None


class AnalyzeCompareResponse(BaseModel):
    symbols: list[str]
    entries: list[AnalyzeCompareEntry]
    highlights: dict[str, str | None] = {}


class AnalyzeTimeSeriesDiagnosticsResponse(BaseModel):
    symbol: str
    lookback: int
    price_bars: int = 0
    return_bars: int = 0
    observations: int = 0
    data_source: str = "none"
    sufficient_data: bool = False
    mean: float | None = None
    annualized_volatility: float | None = None
    skewness: float | None = None
    excess_kurtosis: float | None = None
    jarque_bera: dict[str, Any] = {}
    adf: dict[str, Any] = {}
    autocorrelation: dict[str, Any] = {}
    interpretation: str = "insufficient data"
    notes: list[str] = []


class PortfolioHolding(BaseModel):
    symbol: str
    shares: float = Field(gt=0)
    avg_cost: float = Field(gt=0)
    bucket: Bucket = Bucket.penny


class PortfolioDecisionRequest(BaseModel):
    cash: float = Field(default=0.0, ge=0)
    holdings: list[PortfolioHolding] = Field(default_factory=list)
    persist: bool = False


class PortfolioDecisionItem(BaseModel):
    symbol: str
    bucket: str
    price: float = 0.0
    price_available: bool = True
    shares: float
    avg_cost: float
    market_value: float
    pl_pct: float | None = None
    current_weight: float
    target_weight: float
    buy_pct: float
    keep_pct: float
    sell_pct: float
    decision: str
    suggested_action: str = ""
    score: float
    risk_index: float
    suggested_dollar_action: float
    reasons: list[str] = []
    risk_flags: list[str] = []
    # explainability / debug
    alpha_score: float | None = None
    momentum_score: float | None = None
    liquidity_score: float | None = None
    risk_score: float | None = None
    data_quality_score: float | None = None
    max_allowed_weight: float | None = None
    overweight_penalty: float | None = None
    missing_data_penalty: float | None = None
    stop_loss_trigger: bool = False
    final_buy_raw: float | None = None
    final_keep_raw: float | None = None
    final_sell_raw: float | None = None


class PortfolioDecisionResponse(BaseModel):
    as_of: str
    cash: float
    total_value: float
    invested_value: float = 0.0
    items: list[PortfolioDecisionItem] = []
    notes: list[str] = []


class ClosedPositionItem(BaseModel):
    symbol: str
    total_bought: float = 0.0
    total_sold: float = 0.0
    realized_pl: float = 0.0
    last_activity: str = ""


class PennyOpportunityItem(BaseModel):
    symbol: str
    score: float
    price: float
    setup_type: str | None = None
    summary: str = ""


class DailyDashboardResponse(BaseModel):
    portfolio_value: float = 0.0
    cash: float = 0.0
    invested_value: float = 0.0
    cash_pct: float = 0.0
    active_holdings_count: int = 0
    data_source: str = "manual"
    data_source_label: str = "Manual holdings"
    is_demo_data: bool = False
    last_brokerage_sync_at: str | None = None
    last_decision_run_at: str | None = None
    decision: PortfolioDecisionResponse | None = None
    holdings: list[dict[str, Any]] = []
    closed_positions: list[ClosedPositionItem] = []
    top_penny_opportunities: list[PennyOpportunityItem] = []
    risk_alerts: list[str] = []
    portfolio_warnings: list[str] = []
    disclaimer: str = ""


class BrokerageCsvImportResponse(BaseModel):
    filename: str
    trades_parsed: int = 0
    trades_imported: int = 0
    trades_skipped: int = 0
    holdings_count: int = 0
    holdings: list[dict[str, Any]] = []
    warnings: list[str] = []
    account: dict[str, Any] = {}


class CurrentPortfolioResponse(BaseModel):
    account: dict[str, Any] = {}
    cash: float = 0.0
    holdings: list[dict[str, Any]] = []
    data_source: str = "manual"
    disclaimer: str = ""


class PortfolioDecisionRunResponse(BaseModel):
    ok: bool = True
    trigger: str = "manual"
    decision: PortfolioDecisionResponse
    snapshot_id: int | None = None


class PortfolioDecisionHistoryItem(BaseModel):
    id: int
    trigger: str
    created_at: str
    holding_count: int = 0
