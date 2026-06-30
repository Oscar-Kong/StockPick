// Shared TypeScript types for backend responses and UI state.
export type Bucket = "penny" | "medium" | "compounder";

export type RiskLevel = "low" | "medium" | "high";

export type ScanStatus = "pending" | "running" | "completed" | "failed";

export interface Signal {
  name: string;
  value: number;
  weight: number;
  contribution: number;
  description: string;
}

export interface StockResult {
  symbol: string;
  price: number;
  score: number;
  alpha_score?: number | null;
  confidence_score?: number | null;
  tradability_score?: number | null;
  ranking_score?: number | null;
  signals: Signal[];
  risk_level: RiskLevel;
  summary: string;
  bucket: Bucket;
  metrics: Record<string, unknown>;
  valuation_warnings?: string[];
  earnings_date?: string | null;
  days_until_earnings?: number | null;
  earnings_soon?: boolean;
}

export interface ScanPickSummaryResponse {
  symbol: string;
  bucket: Bucket;
  background: string;
  why_picked: string;
  text: string;
  source: "llm" | "rules" | string;
}

export interface ScanJobResponse {
  job_id: string;
  bucket: Bucket;
  status: ScanStatus;
}

export interface ScanStatusResponse {
  job_id: string;
  bucket: Bucket;
  status: ScanStatus;
  progress: number;
  message: string;
  results: StockResult[];
  completed_at: string | null;
  scoring_engine_used?: boolean | null;
  parity_summary?: ScanParitySummary | null;
}

export interface ScanParityRecord {
  symbol: string;
  sleeve: string;
  legacy_score: number;
  engine_score: number;
  parity_delta: number;
  scoring_engine_used: boolean;
  legacy_recommendation_bucket?: string;
  engine_recommendation_bucket?: string;
  recommendation_bucket_differs?: boolean;
  top_factor_contributions?: {
    factor_id: string;
    display_name: string;
    contribution: number;
    norm_score?: number;
    weight?: number;
  }[];
}

export interface ScanParitySummary {
  scoring_engine_used?: boolean;
  symbol_count?: number;
  average_delta?: number;
  max_delta?: number;
  symbols_delta_gt_10?: number;
  recommendation_bucket_diffs?: number;
  records?: ScanParityRecord[];
}

export interface ScanOptions {
  max_results?: number;
  min_price?: number;
  max_price?: number;
  min_volume?: number;
  exclude_sectors?: string[];
  mode?: "deep" | "fast";
}

/** Active Home portfolio row — used to mark scan hits you already own. */
export interface HeldPositionSummary {
  shares: number;
  avgCost?: number;
}

export interface OHLCPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface StockDetail {
  symbol: string;
  price: number;
  ohlc: OHLCPoint[];
  fundamentals: Record<string, unknown>;
  scores: Record<string, number>;
  explanation: string;
  ai_explanation?: string;
  bucket: Bucket | null;
  earnings_date?: string | null;
  days_until_earnings?: number | null;
  earnings_soon?: boolean;
  valuation_warnings?: string[];
  news_headlines?: string[];
  news_categories?: Record<string, number>;
  backtest?: BacktestResult | MultiHorizonBacktestResponse | null;
  data_quality_score?: number | null;
  strategy_version?: string | null;
}

export interface LatestScanResponse {
  bucket: Bucket;
  results: StockResult[];
  completed_at: string | null;
  strategy_version?: string | null;
  scoring_engine_used?: boolean | null;
  parity_summary?: ScanParitySummary | null;
}

export interface SavedScanItem {
  id: number;
  name: string;
  bucket: Bucket;
  options: Record<string, unknown>;
  results: StockResult[];
  result_count: number;
  strategy_version?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface SavedScanCreateRequest {
  name?: string;
  bucket: Bucket;
  options?: Record<string, unknown>;
  results: StockResult[];
  strategy_version?: string | null;
  completed_at?: string | null;
}

export interface WatchlistItem {
  symbol: string;
  bucket: Bucket;
  notes: string;
  added_at: string;
  price?: number | null;
  score?: number | null;
  summary?: string;
  last_scanned_at?: string | null;
  earnings_date?: string | null;
  days_until_earnings?: number | null;
  valuation_warnings?: string[];
}

export interface WatchlistRefreshResponse {
  refreshed: number;
  failed: number;
  results: Record<string, unknown>[];
}

export interface WatchlistImportRequest {
  input: string;
  bucket?: Bucket | "auto";
  notes?: string;
}

export interface WatchlistImportRow {
  symbol: string;
  bucket: string;
  price?: number | null;
  score?: number | null;
  summary: string;
  notes: string;
  added: boolean;
  error?: string | null;
  report?: StockResearchReport | null;
}

export interface WatchlistImportResponse {
  results: WatchlistImportRow[];
  added_count: number;
  failed_count: number;
}

export interface HealthResponse {
  status: string;
  environment?: string;
  demo_mode?: boolean;
  database?: string;
  version?: string;
  alpha_vantage_configured?: boolean;
  fred_configured?: boolean;
  newsapi_configured?: boolean;
  finnhub_configured?: boolean;
  fmp_configured?: boolean;
  llm_configured?: boolean;
  quandl_configured?: boolean;
  openbb_enabled?: boolean;
  scheduler_enabled?: boolean;
  app_env?: string;
  primary_price_source?: string;
  primary_fundamentals_source?: string;
  primary_news_source?: string;
  database_dialect?: string;
  job_queue_backend?: string;
  redis_connected?: boolean;
  strategy_version?: string;
  factor_model_version?: string;
}

export interface ApiSettingItem {
  key: string;
  label: string;
  description: string;
  enabled: boolean;
  env_default: boolean;
  overridden: boolean;
  configured: boolean | null;
  requires_key: string | null;
}

export interface ApiSettingsGroup {
  id: string;
  title: string;
  description: string;
  items: ApiSettingItem[];
}

export interface ApiSettingsResponse {
  groups: ApiSettingsGroup[];
  primary_price_source: string;
  primary_fundamentals_source: string;
  primary_news_source: string;
  app_env: string;
}

export interface BacktestTearSheet {
  total_return_pct: number;
  annualized_return_pct?: number | null;
  buy_hold_return_pct: number;
  excess_return_vs_buy_hold_pct?: number | null;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  calmar_ratio?: number | null;
  win_rate_pct: number;
  trade_count: number;
  avg_win_pct?: number | null;
  avg_loss_pct?: number | null;
  profit_factor?: number | null;
  validation_passed?: boolean | null;
  in_sample_sharpe?: number | null;
  out_of_sample_sharpe?: number | null;
  entry_variant?: string | null;
  backtest_engine?: string;
}

export interface BacktestResult {
  initial_capital: number;
  final_capital: number;
  total_return_pct: number;
  gross_return_pct?: number | null;
  costs_applied?: boolean;
  annualized_return_pct?: number | null;
  buy_hold_return_pct: number;
  win_rate_pct: number;
  trade_count: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  trades: Record<string, unknown>[];
  message: string;
  horizon?: string | null;
  strategy_version?: string | null;
  entry_variant?: string | null;
  tear_sheet?: BacktestTearSheet | null;
  validation_passed?: boolean | null;
  validation_notes?: string[];
  in_sample?: Record<string, unknown> | null;
  out_of_sample?: Record<string, unknown> | null;
  backtest_engine?: string;
}

export interface MultiHorizonBacktestResponse {
  horizons: Record<string, BacktestResult>;
  overall_passed: boolean;
  strategy_version: string;
  message: string;
}

export interface BacktestSweepRequest {
  horizon?: string;
  entry_variant?: string | null;
  hold_days?: number[];
  stop_pct?: number[];
  target_pct?: (number | null)[];
  max_trials?: number;
  top_k?: number;
}

export interface BacktestSweepItem {
  hold_days: number;
  stop_pct: number;
  target_pct?: number | null;
  total_return_pct: number;
  annualized_return_pct?: number | null;
  sharpe_ratio: number;
  deflated_sharpe?: number | null;
  max_drawdown_pct: number;
  win_rate_pct: number;
  trade_count: number;
  validation_passed?: boolean | null;
  validation_notes?: string[];
  backtest_engine?: string;
}

export interface BacktestSweepDiagnostics {
  n_trials: number;
  median_sharpe: number;
  median_return_pct: number;
  oos_validation_pass_rate: number;
  walk_forward_stable: boolean;
  overfit_risk: string;
  oos_split_ratio: number;
  best_deflated_sharpe?: number | null;
  message: string;
}

export interface BacktestSweepResponse {
  symbol: string;
  bucket: Bucket;
  horizon: string;
  engine: string;
  entry_variant?: string | null;
  strategy_version?: string | null;
  trials: number;
  best?: BacktestSweepItem | null;
  results: BacktestSweepItem[];
  sweep_diagnostics?: BacktestSweepDiagnostics | null;
  message: string;
}

export interface EntryVariantItem {
  id: string;
  label: string;
}

export interface BacktestParamOverrides {
  hold_days?: number;
  stop_pct?: number;
  target_pct?: number | null;
  entry_variant?: string | null;
}

export interface ExplainResponse {
  symbol: string;
  explanation: string;
  source: string;
  sections?: Record<string, string>;
  reasoning?: Record<string, unknown>;
}

export interface SavedReportItem {
  id: number;
  symbol: string;
  bucket?: Bucket | null;
  title: string;
  notes: string;
  report: StockResearchReport | Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SavedReportCreateRequest {
  symbol: string;
  bucket?: Bucket | null;
  title?: string;
  notes?: string;
  report: StockResearchReport | Record<string, unknown>;
}

export interface SavedReportUpdateRequest {
  title?: string;
  notes?: string;
  report?: StockResearchReport | Record<string, unknown>;
}

export interface SavedAnalyzeItem {
  id: number;
  symbol: string;
  bucket: Bucket;
  payload: AnalyzeSymbolResponse;
  score?: number | null;
  data_quality_score?: number | null;
  created_at: string;
  updated_at: string;
}

export interface SavedProgressSummary {
  scan_count: number;
  report_count: number;
  analyze_count: number;
  trade_count: number;
  latest_scan_bucket?: Bucket | null;
  latest_scan_at?: string | null;
  latest_report_symbol?: string | null;
  latest_report_at?: string | null;
  latest_analyze_symbol?: string | null;
  latest_analyze_bucket?: Bucket | null;
  latest_analyze_at?: string | null;
  latest_trade_symbol?: string | null;
  latest_trade_at?: string | null;
}

export interface TraderIntelSource {
  title: string;
  url: string;
  source_type: string;
}

export interface TraderKnownObservation {
  observation: string;
  confidence: string;
}

export interface TraderIntegrationRecipe {
  style: string;
  bucket_bias: string[];
  scan_tilt: Record<string, unknown>;
  risk_controls: string[];
}

export interface TraderProfileItem {
  slug: string;
  name: string;
  aliases: string[];
  profile_type: string;
  data_reliability: string;
  summary: string;
  strategy_principles: string[];
  known_observations: TraderKnownObservation[];
  integration_recipe: TraderIntegrationRecipe;
  sources: TraderIntelSource[];
}

export interface TraderProfileListResponse {
  collected_at_utc: string;
  notes: string[];
  profiles: TraderProfileItem[];
}

export interface TraderPresetResponse {
  slug: string;
  bucket: Bucket;
  scan_options: Record<string, unknown>;
  backtest_overrides: {
    hold_days?: number;
    stop_pct?: number;
    target_pct?: number | null;
  };
  horizon?: string | null;
  notes: string[];
}

export interface TraderBacktestVariantResult {
  hold_days: number;
  stop_pct: number;
  target_pct?: number | null;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  trade_count: number;
  annualized_return_pct?: number | null;
  validation_passed?: boolean | null;
  backtest_engine: string;
}

export interface TraderQuickCompareResponse {
  slug: string;
  bucket: Bucket;
  symbol: string;
  horizon: string;
  baseline: TraderBacktestVariantResult;
  trader_style: TraderBacktestVariantResult;
  delta_total_return_pct: number;
  delta_sharpe_ratio: number;
  notes: string[];
}

export interface TradeReviewSnapshot {
  pnl_abs?: number | null;
  pnl_pct?: number | null;
  planned_rr?: number | null;
  quality_score: number;
  quality_label: string;
  process_good: boolean;
  review_note: string;
  flags: string[];
  image_insight?: string;
  image_tags?: string[];
  image_analysis_status?: string;
}

export interface TradeItem {
  id: number;
  symbol: string;
  side: string;
  entry_time: string;
  exit_time?: string | null;
  entry_price: number;
  exit_price?: number | null;
  quantity?: number | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  setup_tags: string[];
  thesis: string;
  notes: string;
  screenshot_path?: string | null;
  review: TradeReviewSnapshot;
  created_at: string;
  updated_at: string;
  portfolio_synced?: boolean | null;
  portfolio_sync_status?: "synced" | "pending" | "needs_quantity" | null;
}

export interface TradeManualResponse extends TradeItem {
  portfolio_synced?: boolean;
  portfolio_message?: string | null;
}

export interface TradeCreateRequest {
  symbol: string;
  sleeve?: "penny" | "medium" | "compounder" | null;
  side: "long" | "short";
  entry_time: string;
  exit_time?: string | null;
  entry_price: number;
  exit_price?: number | null;
  quantity?: number | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  setup_tags?: string[];
  thesis?: string;
  notes?: string;
}

export interface TradeUpdateRequest {
  exit_time?: string | null;
  exit_price?: number | null;
  quantity?: number | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  setup_tags?: string[];
  thesis?: string;
  notes?: string;
}

export interface TradeStatsResponse {
  total_trades: number;
  closed_trades: number;
  win_rate_pct: number;
  avg_pnl_pct: number;
  avg_quality_score: number;
  strong_process_rate_pct: number;
  profitable_but_weak_count: number;
  disciplined_loss_count: number;
  top_flags: { flag: string; count: number }[];
}

export interface AnalyzeAlert {
  type: string;
  severity: string;
  message: string;
}

export interface AnalyzeWatchlistRow {
  symbol: string;
  bucket: Bucket;
  notes: string;
  price: number | null;
  score: number | null;
  summary: string;
  last_scanned_at: string | null;
  stale: boolean;
  earnings_date: string | null;
  days_until_earnings: number | null;
  valuation_warnings: string[];
  data_quality_score: number | null;
  technicals: Record<string, number | null>;
  alerts: AnalyzeAlert[];
  alert_count: number;
}

export interface AnalyzeWatchlistResponse {
  rows: AnalyzeWatchlistRow[];
  alert_total: number;
}

export interface AnalyzeSymbolResponse {
  symbol: string;
  assigned_bucket: Bucket;
  price: number;
  score: number;
  risk_level: string;
  summary: string;
  signals: Signal[];
  metrics: Record<string, unknown>;
  valuation_warnings: string[];
  earnings_date: string | null;
  days_until_earnings: number | null;
  earnings_soon: boolean;
  data_quality_score: number | null;
  reconcile: Record<string, unknown>;
  technicals: Record<string, number | null>;
  bucket_fit: {
    scores: Record<string, { score: number; passed_hard_filter: boolean; risk_level: string } | null>;
    best_bucket: string | null;
  };
  alerts: AnalyzeAlert[];
  ohlc: OHLCPoint[];
  fundamentals: Record<string, unknown>;
  price_history_last_date?: string | null;
  price_history_source?: string | null;
  price_history_is_stale?: boolean;
  price_history_refreshed_at?: string | null;
  price_history_bar_count?: number;
}

export interface PositionSizingV2 {
  symbol: string;
  sleeve: string;
  recommended_weight_pct: number;
  max_weight_pct: number;
  stop_loss_pct: number;
  portfolio_allocation_pct: number;
  conviction: number;
  sleeve_max_pct: number;
  risk_multiplier: number;
  dq_multiplier: number;
  rationale: string;
}

export interface UnifiedRiskV2 {
  symbol: string;
  sleeve: string;
  risk_index: number;
  safety_score: number;
  deduction_pts: number;
  macro: string[];
  company: string[];
  events: string[];
  score_deductions: { category: string; points: number }[];
  alerts: AnalyzeAlert[];
  breakdown: Record<string, unknown>[];
  volatility?: VolatilityRiskV2 | null;
}

export interface VolatilityRiskV2 {
  sufficient_data?: boolean;
  observations?: number;
  realized_volatility?: number | null;
  ewma_volatility?: number | null;
  downside_volatility?: number | null;
  historical_var?: number | null;
  historical_es?: number | null;
  volatility_regime?: string;
  tail_risk?: boolean;
  risk_penalty_pts?: number;
  window?: number;
  alpha?: number;
}

export interface JarqueBeraResult {
  available: boolean;
  statistic?: number | null;
  pvalue?: number | null;
}

export interface AdfResult {
  available: boolean;
  statistic?: number | null;
  pvalue?: number | null;
}

export interface SymbolDiagnosticsResponse {
  symbol: string;
  lookback: number;
  price_bars: number;
  return_bars: number;
  observations: number;
  data_source: string;
  sufficient_data: boolean;
  mean: number | null;
  annualized_volatility: number | null;
  skewness: number | null;
  excess_kurtosis: number | null;
  jarque_bera: JarqueBeraResult;
  adf: AdfResult;
  autocorrelation: {
    lags?: number[];
    acf?: number[];
    n?: number;
    lag1?: number | null;
  };
  interpretation: string;
  notes: string[];
}

export interface FactorExposureRequest {
  symbols: string[];
  benchmark?: string;
  lookback_period?: "6mo" | "1y" | "2y" | "3y" | "5y";
  correlation_window?: number;
  n_components?: number | null;
  pc1_concentration_threshold?: number;
}

export interface FactorExposureResponse {
  diagnostic_only: boolean;
  benchmark: string;
  lookback_period: string;
  symbols_requested: string[];
  symbols_used: string[];
  excluded: string[];
  observation_count: number;
  betas: Record<
    string,
    {
      beta?: number | null;
      alpha_daily?: number | null;
      r_squared?: number | null;
      observations?: number;
      sufficient?: boolean;
    }
  >;
  correlation: Record<string, unknown>;
  pca: {
    sufficient?: boolean;
    observations?: number;
    n_components?: number;
    explained_variance_ratio?: number[];
    cumulative_explained_variance?: number[];
    symbol_loadings?: Record<string, string | number>[];
    concentration_warning?: boolean;
    pc1_variance_ratio?: number | null;
    pc1_concentration_threshold?: number;
    reason?: string;
  };
  concentration_warning: boolean;
  notes: string[];
}

export interface PillarScoresV2 {
  alpha_score: number;
  valuation_score: number;
  catalyst_score: number;
  momentum?: number | null;
  quality?: number | null;
  growth?: number | null;
  value?: number | null;
  sentiment?: number | null;
  data_quality_penalty?: number;
  liquidity_penalty?: number;
  risk_penalty?: number;
  final_recommendation_score?: number;
  factor_contributions?: Record<string, number>;
}

export interface DataConfidenceV2 {
  data_confidence: number;
  issues: string[];
  strengths?: string[];
  strong_recommendation_allowed?: boolean;
  strong_buy_allowed?: boolean;
}

export interface RecommendationV2 {
  recommendation: string;
  confidence: number;
  time_horizon_days: number;
  expected_return_pct: number;
  expected_downside_pct: number;
  pillars: PillarScoresV2;
  data_confidence: DataConfidenceV2;
  gates: string[];
  bull_case: string;
  bear_case: string;
}

export interface ValuationV2 {
  dcf_fair_value?: number | null;
  dcf_bull?: number | null;
  dcf_bear?: number | null;
  peer_fair_value?: number | null;
  reverse_dcf_implied_growth_pct?: number | null;
  margin_of_safety_pct?: number | null;
  premium_to_peers_pct?: number | null;
  valuation_score?: number;
  verdict?: string;
  assumptions?: Record<string, unknown>;
  sensitivity_grid?: {
    wacc?: number[];
    terminal_growth?: number[];
    values?: (number | null)[][];
  };
}

export interface SimilarSignalV2 {
  sample_n: number;
  avg_forward_return_pct?: number | null;
  win_rate?: number | null;
  max_drawdown_pct?: number | null;
  forward_days?: number;
  top_analogs?: { symbol: string; date: string; forward_return_pct?: number }[];
}

export interface PortfolioImpactV2 {
  correlation_with_portfolio?: number | null;
  sector_exposure_after_pct?: number | null;
  portfolio_beta_impact?: number | null;
  holdings_source?: string;
  holdings_used?: string[];
}

export interface FactorContributionV2 {
  factor_id: string;
  display_name: string;
  norm_score: number;
  weight: number;
  contribution: number;
  description?: string;
}

export interface ScoreAttributionV2 {
  raw_score: number;
  regime_mult: number;
  sector_tilt: number;
  dq_multiplier: number;
  openbb_delta?: number;
  score_after_regime: number;
  score_after_dq: number;
  risk_deduction: number;
  final_score: number;
}

export interface RiskBreakdownV2 {
  risk_score: number;
  deduction_pts: number;
  items: Record<string, unknown>[];
}

export interface V2ScoreResponse {
  symbol: string;
  sleeve: string;
  score: number;
  market_regime?: string | null;
  dynamic_weights?: boolean;
  recommendation?: RecommendationV2 | null;
  valuation?: ValuationV2 | null;
  earnings_setup?: Record<string, unknown>;
  similar_signal?: SimilarSignalV2 | null;
  portfolio_impact?: PortfolioImpactV2 | null;
  position_sizing?: PositionSizingV2 | null;
  prediction_snapshot_id?: number | null;
  summary: string;
  risk_level: string;
  factors: FactorContributionV2[];
  attribution: ScoreAttributionV2;
  risk: RiskBreakdownV2;
  alerts?: { type?: string; severity?: string; message?: string }[];
  strategy_version?: string;
  factor_model_version?: string;
  parity_delta?: number | null;
  metrics?: Record<string, unknown>;
  agents?: Record<string, unknown> | null;
}

export interface AnalyzeCompareEntry {
  symbol: string;
  assigned_bucket?: string | null;
  price?: number | null;
  score?: number | null;
  risk_level?: string | null;
  passed_hard_filter?: boolean | null;
  summary?: string | null;
  reconcile_quality?: number | null;
  canonical?: Record<string, number | null>;
  technicals?: Record<string, number | null>;
  alert_count?: number;
  stale?: boolean;
  valuation_warnings?: string[];
  on_watchlist?: boolean;
  error?: string | null;
}

export interface AnalyzeCompareResponse {
  symbols: string[];
  entries: AnalyzeCompareEntry[];
  highlights?: Record<string, string | null>;
}

export interface PortfolioOptimizeRequest {
  symbols: string[];
  objective?: "max_sharpe" | "min_vol" | "risk_parity" | "target_return" | "kelly";
  kelly_overlay?: boolean;
  max_weight?: number;
  cash_buffer?: number;
  target_return?: number | null;
  lookback_period?: "6mo" | "1y" | "2y" | "3y" | "5y";
}

export interface PortfolioOptimizeItem {
  symbol: string;
  weight: number;
  annual_return?: number | null;
  annual_volatility?: number | null;
}

export interface PortfolioOptimizeResponse {
  objective: string;
  optimizer: string;
  symbols_requested: string[];
  symbols_used: string[];
  excluded: string[];
  weights: PortfolioOptimizeItem[];
  expected_return?: number | null;
  expected_volatility?: number | null;
  expected_sharpe?: number | null;
  constraints: Record<string, unknown>;
  notes: string[];
}

export interface PortfolioPolicyBacktestRequest {
  symbols: string[];
  policy?: "equal_weight" | "inverse_vol" | "top_n_momentum";
  rebalance?: "weekly" | "monthly";
  top_n?: number;
  lookback_period?: "6mo" | "1y" | "2y" | "3y" | "5y";
  initial_capital?: number;
  max_weight?: number;
  cash_buffer?: number;
  institutional?: boolean;
  sleeve?: "penny" | "medium" | "compounder";
  fee_bps?: number;
  slip_bps?: number;
  use_universe_pit?: boolean;
}

export interface PortfolioPolicyBacktestResponse {
  policy: string;
  rebalance: string;
  engine: string;
  lookback_period: string;
  symbols_requested: string[];
  symbols_used: string[];
  excluded: string[];
  initial_capital: number;
  final_capital: number;
  total_return_pct: number;
  annualized_return_pct: number;
  max_drawdown_pct: number;
  volatility_pct: number;
  sharpe_ratio: number;
  benchmark_return_pct: number;
  turnover_pct: number;
  rebalance_count: number;
  equity_curve: { date: string; equity: number }[];
  benchmark_equity_curve?: { date: string; equity: number }[];
  start_date?: string | null;
  end_date?: string | null;
  weights_history: { date: string; weights: Record<string, number> }[];
  notes: string[];
  sortino_ratio?: number | null;
  calmar_ratio?: number | null;
  beta?: number | null;
  alpha_vs_spy_pct?: number | null;
  total_cost_pct?: number | null;
  total_cost_usd?: number | null;
  run_id?: string | null;
  cost_events?: { date: string; notional?: number; cost_usd?: number; note?: string }[];
  institutional?: boolean;
}

export type PortfolioSourceType = "current" | "watchlist" | "custom";

export interface PortfolioPositionSummary {
  symbol: string;
  company_name?: string | null;
  shares: number;
  price?: number | null;
  market_value?: number | null;
  avg_cost?: number | null;
  unrealized_pl_pct?: number | null;
  weight?: number | null;
  daily_change_pct?: number | null;
  bucket?: string | null;
  price_available?: boolean;
}

export interface PortfolioSummaryResponse {
  as_of: string;
  price_as_of?: string | null;
  total_value: number;
  invested_value: number;
  cash: number;
  reserved_cash?: number;
  cash_weight: number;
  today_change_pct?: number | null;
  total_unrealized_pl_pct?: number | null;
  active_holdings_count: number;
  largest_position?: string | null;
  largest_position_weight?: number | null;
  largest_sector?: string | null;
  portfolio_beta?: number | null;
  estimated_annual_volatility?: number | null;
  holdings_updated_at?: string | null;
  last_price_update_at?: string | null;
  risk_model_through?: string | null;
  positions: PortfolioPositionSummary[];
  source: string;
  data_source: string;
  data_source_label: string;
  is_demo_data?: boolean;
  stale: boolean;
  warnings: string[];
  freshness?: Record<string, unknown> | null;
  disclaimer: string;
}

export interface RebalanceHoldingInput {
  symbol: string;
  shares: number;
  avg_cost?: number | null;
  price?: number | null;
}

export interface RebalancePreviewRequest {
  holdings: RebalanceHoldingInput[];
  target_weights: Record<string, number>;
  cash: number;
  cash_reserve?: number;
  min_trade_amount?: number;
  fractional_shares?: boolean;
  fee_bps?: number;
  slippage_bps?: number;
  max_turnover?: number | null;
}

export interface RebalanceTradeItem {
  symbol: string;
  current_shares: number;
  current_price: number;
  current_value: number;
  current_weight: number;
  target_weight: number;
  weight_difference: number;
  target_value: number;
  dollar_trade: number;
  share_trade: number;
  action: "buy" | "sell" | "hold";
  estimated_fee: number;
  estimated_slippage: number;
  post_trade_weight: number;
}

export interface RebalancePreviewResponse {
  total_value: number;
  cash_before: number;
  cash_after: number;
  cash_reserve: number;
  turnover_pct: number;
  estimated_fees: number;
  estimated_slippage: number;
  trade_count: number;
  trades: RebalanceTradeItem[];
  constraint_violations: string[];
  warnings: string[];
  model_version: string;
}

export interface ApiStructuredError {
  error: string;
  message: string;
  request_id?: string;
  retryable?: boolean;
}

export interface PortfolioHolding {
  symbol: string;
  shares: number;
  avg_cost: number;
  bucket: Bucket;
}

export interface PortfolioDecisionRequest {
  cash?: number;
  holdings: PortfolioHolding[];
  persist?: boolean;
}

export interface PortfolioDecisionItem {
  symbol: string;
  bucket: string;
  price: number;
  price_available?: boolean;
  shares: number;
  avg_cost: number;
  market_value: number;
  pl_pct?: number | null;
  current_weight: number;
  target_weight: number;
  buy_pct: number;
  keep_pct: number;
  sell_pct: number;
  decision: string;
  suggested_action?: string;
  score: number;
  risk_index: number;
  suggested_dollar_action: number;
  reasons: string[];
  risk_flags: string[];
  alpha_score?: number | null;
  momentum_score?: number | null;
  liquidity_score?: number | null;
  risk_score?: number | null;
  data_quality_score?: number | null;
  max_allowed_weight?: number | null;
  overweight_penalty?: number | null;
  missing_data_penalty?: number | null;
  stop_loss_trigger?: boolean;
  final_buy_raw?: number | null;
  final_keep_raw?: number | null;
  final_sell_raw?: number | null;
}

export interface PortfolioDecisionResponse {
  as_of: string;
  cash: number;
  total_value: number;
  invested_value?: number;
  items: PortfolioDecisionItem[];
  notes: string[];
}

export interface ClosedPositionItem {
  symbol: string;
  total_bought: number;
  total_sold: number;
  realized_pl: number;
  last_activity?: string;
}

export interface PennyOpportunityItem {
  symbol: string;
  score: number;
  price: number;
  setup_type?: string | null;
  summary?: string;
}

export type DataFreshnessOverallStatus = "fresh" | "updating" | "stale" | "missing" | "demo";

export interface DataFreshnessStatus {
  key: string;
  last_updated_at?: string | null;
  stale_after_seconds?: number | null;
  is_stale: boolean;
  is_missing: boolean;
  reason: string;
  source: string;
}

export interface DashboardFreshnessSummary {
  overall_status: DataFreshnessOverallStatus;
  items: DataFreshnessStatus[];
  refresh_recommended: boolean;
  refresh_in_progress: boolean;
  refresh_job_id?: string | null;
  last_holdings_sync_at?: string | null;
  last_price_update_at?: string | null;
  last_decision_run_at?: string | null;
  last_penny_scan_at?: string | null;
}

export interface HomeRefreshResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface HomeRefreshStatusResponse {
  job_id: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export interface DailyDashboardResponse {
  portfolio_value: number;
  cash: number;
  reserved_cash?: number;
  ipo_shares?: number | null;
  ipo_list_price?: number | null;
  ipo_buffer?: number;
  invested_value?: number;
  cash_pct?: number;
  active_holdings_count?: number;
  data_source: string;
  data_source_label: string;
  is_demo_data?: boolean;
  last_brokerage_sync_at?: string | null;
  last_decision_run_at?: string | null;
  decision?: PortfolioDecisionResponse | null;
  holdings: Array<{ symbol: string; shares: number; avg_cost: number; bucket: string }>;
  closed_positions?: ClosedPositionItem[];
  top_penny_opportunities: PennyOpportunityItem[];
  risk_alerts?: string[];
  portfolio_warnings: string[];
  disclaimer: string;
  freshness?: DashboardFreshnessSummary | null;
  decision_stale_warning?: string | null;
  csv_rows_loaded?: number | null;
  ledger_rows_count?: number | null;
  ledger_cash_estimate?: number | null;
  cash_source?: string | null;
}

export interface BrokerageCsvImportResponse {
  filename: string;
  trades_parsed: number;
  trades_imported: number;
  trades_skipped: number;
  holdings_count: number;
  holdings: Array<{ symbol: string; shares: number; avg_cost: number; bucket: string }>;
  warnings: string[];
  account: Record<string, unknown>;
}

export interface LedgerEntry {
  id: number;
  symbol: string;
  side: string;
  row_type: string;
  quantity: number | null;
  price: number | null;
  amount: number | null;
  trans_code: string | null;
  description: string | null;
  activity_date: string | null;
  process_date: string | null;
  executed_at: string | null;
  source: string;
  row_hash: string;
  locked: boolean;
}

export interface LedgerListResponse {
  rows: LedgerEntry[];
  open_holdings: Array<{ symbol: string; shares: number; avg_cost: number; bucket?: string }>;
  closed_positions: Array<{
    symbol: string;
    total_bought: number;
    total_sold: number;
    realized_pl: number;
    last_activity: string;
  }>;
  ledger_cash_estimate: number;
  warnings: string[];
}

export interface LedgerEntryInput {
  symbol: string;
  side: string;
  quantity?: number | null;
  price?: number | null;
  amount?: number | null;
  trans_code?: string | null;
  description?: string | null;
  activity_date?: string | null;
  process_date?: string | null;
  lock?: boolean;
}

export interface CsvPreviewRow {
  client_id: string;
  included: boolean;
  is_new: boolean;
  symbol: string;
  side: string;
  row_type: string;
  quantity: number | null;
  price: number | null;
  amount: number | null;
  trans_code: string | null;
  description: string | null;
  activity_date: string | null;
  process_date: string | null;
  row_hash: string;
}

export interface CsvPreviewResponse {
  filename: string;
  rows: CsvPreviewRow[];
  warnings: string[];
  current_holdings: Array<{ symbol: string; shares: number; avg_cost: number }>;
  projected_holdings: Array<{ symbol: string; shares: number; avg_cost: number }>;
  current_cash_estimate: number;
  projected_cash_estimate: number;
  new_row_count: number;
  skipped_existing_count: number;
}

export interface CsvApproveRequest {
  filename: string;
  replace: boolean;
  cash?: number | null;
  rows: CsvPreviewRow[];
}

export interface PortfolioDecisionRunResponse {
  ok: boolean;
  trigger: string;
  decision: PortfolioDecisionResponse;
  snapshot_id?: number | null;
}

export interface AlphaSignalItem {
  symbol: string;
  alpha_score: number;
  rank: number;
  source: string;
}

export interface AlphaLatestResponse {
  bucket: Bucket;
  as_of: string;
  model_name: string;
  model_version: string;
  enabled: boolean;
  items: AlphaSignalItem[];
  notes: string[];
}

export interface AlphaIngestItem {
  symbol: string;
  alpha_score: number;
  rank?: number | null;
}

export interface AlphaIngestRequest {
  bucket?: Bucket;
  as_of?: string | null;
  model_version?: string;
  items: AlphaIngestItem[];
}

export interface AlphaIngestResponse {
  ok: boolean;
  bucket: Bucket;
  model_version: string;
  ingested: number;
  message: string;
}

export interface AllocationRecommendationItem {
  symbol: string;
  target_weight: number;
  score?: number | null;
  confidence?: number | null;
}

export interface AllocationRecommendationResponse {
  bucket: Bucket;
  as_of: string;
  model_name: string;
  model_version: string;
  enabled: boolean;
  source: string;
  symbols_used: string[];
  excluded: string[];
  target_weights: AllocationRecommendationItem[];
  constraints: Record<string, unknown>;
  notes: string[];
}

export interface LeanExportRequest {
  bucket?: Bucket;
  symbols?: string[];
  rebalance?: "weekly" | "monthly";
  objective?: "max_sharpe" | "min_vol" | "target_return";
  lookback_period?: "6mo" | "1y" | "2y" | "3y" | "5y";
  max_weight?: number;
  cash_buffer?: number;
  include_alpha?: boolean;
  include_latest_scan?: boolean;
  export_name?: string | null;
  notes?: string;
}

export interface LeanExportResponse {
  export_id: string;
  created_at: string;
  bucket: Bucket;
  symbols: string[];
  strategy_version?: string | null;
  file_path: string;
  payload: Record<string, unknown>;
  message: string;
}

export interface LeanImportSummaryRequest {
  export_id: string;
  status?: string;
  metrics?: Record<string, unknown>;
  notes?: string;
}

export interface LeanImportSummaryResponse {
  ok: boolean;
  export_id: string;
  status: string;
  summary_path: string;
  message: string;
}

export interface StockResearchReport {
  symbol: string;
  generated_at?: string;
  assigned_bucket?: string;
  quant_score?: number;
  data_quality_score?: number | null;
  error?: string;
  alerts?: AnalyzeAlert[];
  "1_overview"?: {
    symbol: string;
    company_name?: string;
    sector?: string;
    industry?: string;
    price?: number;
    market_cap?: number;
    high_52w?: number;
    low_52w?: number;
    business_summary?: string;
  };
  "2_industry_positioning"?: Record<string, unknown>;
  "3_fundamentals"?: {
    valuation?: { pe?: number; pb?: number; pe_vs_history_note?: string };
    profitability?: { roe?: number; gross_margin?: number; net_margin?: number };
    growth?: { revenue_yoy?: number; earnings_yoy?: number };
    financial_health?: Record<string, unknown>;
    flags?: string[];
  };
  "4_technical_structure"?: Record<string, unknown>;
  "5_institutional_liquidity"?: Record<string, unknown>;
  "6_news_sentiment"?: {
    earnings_date?: string;
    market_sentiment?: string;
    news_headlines?: string[];
    price_target_note?: string;
    analyst_consensus?: string;
  };
  "7_valuation_zones"?: {
    undervalued_buy_zone?: string;
    fair_value_hold_zone?: string;
    overvalued_reduce_zone?: string;
    current_zone?: string;
  };
  "8_risk_outlook"?: {
    top_risks?: string[];
    conclusion?: string;
    strategy_guidance?: string;
  };
  alignment_notes?: Record<string, string>;
  recommendation?: RecommendationV2 | Record<string, unknown>;
  valuation_analysis?: ValuationV2 | Record<string, unknown>;
  earnings_setup?: Record<string, unknown>;
  similar_signal_backtest?: SimilarSignalV2 | Record<string, unknown>;
  position_sizing?: PositionSizingV2;
}

// --- Quant v2 research & ops (aligned with backend/models/schemas_v2.py) ---

export interface MarketRegimeV2 {
  regime: string;
  as_of_date: string;
  features?: Record<string, unknown>;
}

export interface SleeveWeightsV2 {
  sleeve: string;
  regime: string;
  dynamic_enabled: boolean;
  weights: Record<string, number>;
  weights_by_regime?: Record<string, Record<string, number>> | null;
}

export interface HardFilterRule {
  filter_id: string;
  action: string;
  description: string;
}

export interface HardFiltersResponse {
  sleeve: string;
  rules: HardFilterRule[];
}

export interface FactorIcHorizonEntry {
  factor_id: string;
  sleeve: string;
  horizon_days: number;
  ic: number | null;
  ir: number | null;
  hit_rate: number | null;
  sample_n: number;
  deciles?: { decile: number; avg_forward_return_pct: number; sample_n: number }[];
}

export interface FactorPerformanceFactor {
  factor_id: string;
  sleeve: string | null;
  horizons: Record<string, FactorIcHorizonEntry>;
}

export interface FactorPerformanceResponse {
  as_of_date: string | null;
  horizons: number[];
  factors: FactorPerformanceFactor[];
  by_horizon: Record<string, FactorIcHorizonEntry[]>;
  by_regime: Record<string, unknown[]>;
  by_sector: Record<string, unknown[]>;
  market_regime?: { regime: string; as_of_date: string } | null;
  summary?: Record<string, { mean_ic?: number; positive_ic_count?: number; factor_count?: number }>;
}

export interface PredictionOutcomeSnapshot {
  return_20d?: number | null;
  return_60d?: number | null;
  excess_vs_spy_60d?: number | null;
}

export interface PredictionSnapshotItem {
  id: number;
  symbol: string;
  sleeve: string;
  source: string;
  created_at: string;
  price?: number | null;
  recommendation?: string | null;
  confidence?: number | null;
  alpha_score?: number | null;
  valuation_score?: number | null;
  data_confidence?: number | null;
  trade_id?: number | null;
  outcome: PredictionOutcomeSnapshot | null;
  /** Legacy fields — prefer alpha_score / outcome */
  score?: number;
  as_of_date?: string;
  horizon_days?: number | null;
  resolved?: boolean;
  realized_return_pct?: number | null;
  forecast_error_pct?: number | null;
  resolved_at?: string | null;
}

export interface PredictionsListResponse {
  predictions: PredictionSnapshotItem[];
}

export interface FeedbackOutcomeItem {
  trade_id: number;
  actual_return_pct?: number | null;
  prediction_error_pct?: number | null;
  closed_at?: string | null;
}

export interface FeedbackSummaryResponse {
  outcomes_count: number;
  snapshots_count: number;
  mean_actual_return_pct?: number | null;
  mean_prediction_error_pct?: number | null;
  recent_outcomes: FeedbackOutcomeItem[];
  recent_snapshots: PredictionSnapshotItem[];
  /** Legacy / optional */
  enabled?: boolean;
  unresolved_count?: number;
  resolved_count?: number;
  by_horizon?: Record<string, { count?: number; avg_error_pct?: number; hit_rate?: number }>;
  by_bucket?: Record<string, { count?: number; avg_error_pct?: number }>;
  stale?: boolean;
  last_resolved_at?: string | null;
  notes?: string[];
  [key: string]: unknown;
}

export interface WalkForwardResearchRequest {
  sleeve: Bucket;
  start_date: string;
  end_date: string;
  rebalance_frequency?: string;
  forward_horizons?: number[];
  max_symbols?: number;
  persist_snapshots?: boolean;
}

export interface WalkForwardResearchResponse {
  run_id: string;
  status: string;
  sleeve: string;
  start_date: string;
  end_date: string;
  rebalance_frequency: string;
  forward_horizons: number[];
  rebalance_periods: number;
  periods_scored: number;
  snapshots_written: number;
  mean_turnover?: number | null;
  aggregate_horizons?: Record<string, unknown>;
  periods?: Record<string, unknown>[];
  strategy_version?: string;
  factor_model_version?: string;
  weights_updated?: boolean;
}

export interface WalkForwardRunDetailResponse {
  run_id: string;
  run_type: string;
  config?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  started_at?: string | null;
  finished_at?: string | null;
}

export type QuantLabTrustIndicator =
  | "fresh"
  | "stale"
  | "insufficient_sample"
  | "feature_disabled"
  | "no_saved_run"
  | "research_only"
  | "needs_attention";

export interface QuantLabMainMetric {
  label: string;
  value: string;
}

export interface QuantLabLastRunSummary {
  id: string;
  available: boolean;
  reason?: string | null;
  generated_at?: string | null;
  run_id?: string | null;
  sleeve?: string | null;
  status?: string | null;
  sample_size?: number | null;
  main_metric?: QuantLabMainMetric | null;
  stale: boolean;
  stale_reason?: string | null;
  warnings: string[];
  trust_indicator: QuantLabTrustIndicator;
  research_only: boolean;
  tab?: string | null;
}

export interface QuantLabEvidenceResponse {
  sleeve: string;
  generated_at: string;
  validation_copy: string;
  factor_ic: QuantLabLastRunSummary;
  walk_forward: QuantLabLastRunSummary;
  predictions: QuantLabLastRunSummary;
  pairs: QuantLabLastRunSummary;
  jobs: QuantLabLastRunSummary;
}

export interface PairResearchItem {
  pair: string[];
  symbol_y: string;
  symbol_x: string;
  hedge_ratio?: number | null;
  intercept?: number | null;
  p_value?: number | null;
  cointegrated_5pct?: boolean;
  half_life_sessions?: number | null;
  mean_reverting?: boolean | null;
  latest_z_score?: number | null;
  zscore_window?: number | null;
  spread_mean?: number | null;
  spread_std?: number | null;
  observations?: number;
  sufficient?: boolean;
  engine?: string | null;
  warning?: string | null;
}

export interface PairsResearchRequest {
  symbols: string[];
  lookback_period?: "6mo" | "1y" | "2y" | "3y" | "5y";
  zscore_window?: number;
  max_pairs?: number | null;
  p_value_threshold?: number | null;
}

export interface PairsResearchResponse {
  research_only: boolean;
  lookback_period: string;
  symbols_requested: string[];
  symbols_used: string[];
  excluded: string[];
  observation_count: number;
  pairs_evaluated: number;
  pairs_returned: number;
  cointegrated_count: number;
  insufficient_count: number;
  statsmodels_available: boolean;
  pairs: PairResearchItem[];
  notes: string[];
}

export interface JobLogEntry {
  job_name: string;
  status: string;
  message?: string;
  symbols_processed?: number;
  errors?: number;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface SchedulerStatusResponse {
  enabled: boolean;
  recent_jobs: JobLogEntry[];
  quandl_configured?: boolean;
}

export interface MorningScanEmailDeliveryItem {
  id: number;
  notification_type: string;
  market_date: string;
  status: string;
  provider?: string;
  attempt_count?: number;
  error_code?: string | null;
  error_summary?: string | null;
  is_resend?: boolean;
  is_dry_run?: boolean;
  created_at?: string | null;
  sent_at?: string | null;
}

export interface MorningScanEmailStatusResponse {
  enabled: boolean;
  configured: boolean;
  config_errors: string[];
  provider: string;
  recipient_masked: string;
  schedule_label: string;
  cron: string;
  timezone: string;
  buckets: string[];
  top_n: number;
  scheduler_active: boolean;
  next_run_at: string | null;
  last_successful_delivery: MorningScanEmailDeliveryItem | null;
  last_attempted_delivery: MorningScanEmailDeliveryItem | null;
  scan_freshness: Record<string, { cache_age_seconds?: number | null; stale?: boolean }>;
}

export interface MorningScanEmailSendResponse {
  status: string;
  message: string;
  delivery_id?: number | null;
  dry_run?: boolean;
  subject?: string | null;
  html_preview?: string | null;
  text_preview?: string | null;
}

export interface V2VersionResponse {
  strategy_version: string;
  factor_model_version: string;
  database_dialect?: string;
  job_queue_backend?: string;
  redis_connected?: boolean;
  [key: string]: unknown;
}

export interface V2AuditEvent {
  id?: number;
  event_type?: string;
  symbol?: string | null;
  payload?: Record<string, unknown>;
  created_at?: string;
  [key: string]: unknown;
}

export interface V2AuditResponse {
  events: V2AuditEvent[];
}

export interface V2FactorsAdminResponse {
  factors: unknown[];
  trade_predictions_count: number;
  trade_outcomes_count: number;
  sleeve_filter?: string | null;
  outcome_feedback_preview?: unknown;
}

export interface V2JobsQueueResponse {
  backend: string;
  jobs: Record<string, unknown>[];
}

export interface SimilarSignalBacktestResponse extends SimilarSignalV2 {
  symbol?: string;
  sleeve?: string;
  analogs?: Record<string, unknown>[];
  notes?: string[];
  research_only?: boolean;
}

export type QuantHealthSeverity = "ok" | "warning" | "error";

export interface QuantHealthSection {
  id: string;
  label: string;
  severity: QuantHealthSeverity;
  message: string;
  detail?: string | null;
  as_of?: string | null;
}

export interface QuantHealthSummary {
  overall: QuantHealthSeverity;
  checked_at: string;
  sections: QuantHealthSection[];
  health?: HealthResponse | null;
  latest_scans?: Partial<Record<Bucket, LatestScanResponse | null>>;
  progress?: SavedProgressSummary | null;
  factor_ic_as_of?: string | null;
}

export type ResearchIdeaStatus =
  | "new"
  | "saved"
  | "ready_to_test"
  | "running"
  | "supported"
  | "rejected"
  | "inconclusive"
  | "archived";

export type ResearchIdeaSourceType =
  | "factor_deterioration"
  | "factor_improvement"
  | "prediction_drift"
  | "recommendation_calibration"
  | "market_regime"
  | "scan_dispersion"
  | "portfolio_concentration"
  | "pair_relationship"
  | "data_quality"
  | "failed_experiment"
  | "user_created";

export interface ResearchIdea {
  id: string;
  title: string;
  hypothesis: string;
  description: string;
  why_now: string;
  source_type: ResearchIdeaSourceType;
  source_references: string[];
  sleeve: string | null;
  universe_definition: Record<string, unknown>;
  suggested_experiment_type: string | null;
  suggested_parameters: Record<string, unknown>;
  priority: number;
  confidence: number;
  status: ResearchIdeaStatus;
  user_notes: string;
  created_at: string;
  updated_at: string;
}

export interface ResearchBriefFinding {
  finding_id: string;
  title: string;
  explanation: string;
  supporting_metric: string;
  source_reference: string;
  why_it_matters: string;
  confidence: number;
  evidence_impact: string;
  suggested_experiment_type: string;
  suggested_parameters: Record<string, unknown>;
}

export interface ResearchActivityItem {
  id: string;
  activity_type: string;
  label: string;
  occurred_at?: string | null;
  status?: string | null;
  run_id?: string | null;
}

export interface EvidenceMaintenanceAction {
  action_id: string;
  label: string;
  description: string;
  endpoint: string;
  method: string;
  available: boolean;
  reason_unavailable?: string | null;
}

export interface ResearchOverviewResponse {
  generated_at: string;
  sleeve: string;
  research_confidence_status: string;
  research_confidence_score: number;
  data_freshness: string;
  strategy_version: string;
  factor_model_version: string;
  market_regime?: string | null;
  predictions_resolved: number;
  predictions_unresolved: number;
  failed_or_blocked_jobs: number;
  factor_ic?: QuantLabLastRunSummary | null;
  walk_forward?: QuantLabLastRunSummary | null;
  pairs?: QuantLabLastRunSummary | null;
  major_warnings: string[];
  findings: ResearchBriefFinding[];
  recommended_ideas: ResearchIdea[];
  recent_activity: ResearchActivityItem[];
  maintenance_actions: EvidenceMaintenanceAction[];
}

export interface ResearchIdeaListResponse {
  ideas: ResearchIdea[];
  total: number;
  offset: number;
  limit: number;
}

export interface GenerateIdeasResponse {
  created: ResearchIdea[];
  skipped_duplicates: number;
  findings_used: number;
}

export interface ExperimentTemplateInfo {
  experiment_type: string;
  title: string;
  description: string;
  required_fields: string[];
  optional_fields: string[];
  universe_sources: string[];
  supports_presets: boolean;
}

export interface PresetParameterValue {
  key: string;
  value: string | number | boolean | unknown[];
  description?: string;
}

export interface ExperimentPresetInfo {
  preset_id: string;
  title: string;
  description: string;
  major_evidence_eligible: boolean;
  verdict_ceiling: string;
  parameters: PresetParameterValue[];
}

export interface ExperimentValidationCheck {
  key: string;
  label: string;
  value?: string | number | boolean | null;
  status: "ok" | "warning" | "error" | "missing";
  detail?: string;
}

export interface ExperimentValidationResponse {
  valid: boolean;
  can_run: boolean;
  symbol_count: number;
  missing_data_rate?: number | null;
  expected_periods?: number | null;
  data_cutoff?: string | null;
  dependency_availability: Record<string, boolean>;
  major_limitations: string[];
  checks: ExperimentValidationCheck[];
  resolved_universe: string[];
  merged_parameters: Record<string, unknown>;
}

export interface ExperimentStageRecord {
  stage: string;
  status: string;
  message?: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ExperimentJobResponse {
  job_id: string;
  experiment_id: string;
  status: string;
  current_stage?: string | null;
  stages: ExperimentStageRecord[];
  run_id?: string | null;
  last_success_run_id?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ExperimentLaunchResponse {
  job_id: string;
  experiment_id: string;
  status: string;
  duplicate_blocked: boolean;
  message: string;
}

export type ResearchVerdict =
  | "supports_hypothesis"
  | "rejects_hypothesis"
  | "inconclusive"
  | "insufficient_data"
  | "invalid";

export interface ResearchRunMetric {
  label: string;
  value: string | number;
}

export interface ResearchRunListItem {
  run_id: string;
  experiment_id?: string | null;
  idea_id?: string | null;
  run_type: string;
  name: string;
  status: string;
  verdict?: string | null;
  evidence_impact: string;
  reliability?: Record<string, unknown> | null;
  sleeve?: string | null;
  universe: string[];
  parameters: Record<string, unknown>;
  strategy_version: string;
  factor_model_version: string;
  data_cutoff?: string | null;
  sample_size?: number | null;
  primary_metrics: ResearchRunMetric[];
  warnings: string[];
  blockers: string[];
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  archived: boolean;
  research_notes: string;
  reliability_score?: number | null;
  result_reference: { store: string; run_id: string; detail_path?: string | null };
}

export interface ResearchRunListResponse {
  runs: ResearchRunListItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface ResearchRunReliability {
  score: number;
  status: string;
  reasons: string[];
}

export interface ResearchRunInterpretation {
  verdict: ResearchVerdict;
  conclusion: string;
  evidence_impact: string;
  reliability: ResearchRunReliability;
  supporting_observations: string[];
  main_limitation: string;
  suggested_next_action: string;
  major_evidence_gate: Record<string, unknown>;
  prose?: string | null;
}

export interface ChartSeries {
  chart_id: string;
  title: string;
  chart_type: "line" | "bar" | "heatmap" | "scatter" | "area";
  x_label?: string;
  y_label?: string;
  series: Array<{ name: string; data: Array<{ x: string | number; y?: number | null; label?: string | null }> }>;
  empty_reason?: string | null;
}

export interface MetricExplanation {
  metric_key: string;
  label: string;
  measures: string;
  preferred_direction: string;
  why_it_matters: string;
  limitations: string;
}

export interface ResearchRunDetailResponse {
  summary: ResearchRunListItem;
  interpretation: ResearchRunInterpretation;
  experiment?: Record<string, unknown> | null;
  detail: Record<string, unknown>;
  charts: ChartSeries[];
  metric_explanations: MetricExplanation[];
  evidence_memory: Array<Record<string, unknown>>;
  related_runs: ResearchRunListItem[];
  related_ideas: ResearchIdea[];
  skipped_data: string[];
}

export interface RunComparisonMetricDiff {
  label: string;
  values: Record<string, string | number | null>;
  comparable: boolean;
  note: string;
}

export interface ResearchRunCompareDetailResponse {
  run_ids: string[];
  comparable: boolean;
  compatibility_checks: ExperimentValidationCheck[];
  comparison_notes: string[];
  parameter_diffs: RunComparisonMetricDiff[];
  metric_diffs: RunComparisonMetricDiff[];
  runs: ResearchRunListItem[];
  conclusion: string;
  shared_sleeve?: string | null;
  shared_run_types: string[];
  charts: ChartSeries[];
}

export interface FactorHealthItem {
  factor_id: string;
  display_name: string;
  lifecycle: string;
  production_weight?: number | null;
  recent_ic?: number | null;
  long_term_ic?: number | null;
  sample_size?: number | null;
  drift?: number | null;
  horizon_stability: string;
  regime_stability: string;
  factor_version: string;
  transformation_lineage: string;
  last_calculation?: string | null;
  last_reliable_validation_run_id?: string | null;
  supporting_run_ids: string[];
}

export interface PredictionHealthSummary {
  resolved_count: number;
  unresolved_count: number;
  stale_count: number;
  coverage_pct?: number | null;
  mean_forecast_error_pct?: number | null;
  recommendation_outcomes?: Record<string, number>;
  horizon_breakdown?: Record<string, unknown>;
  regime_breakdown?: Record<string, unknown>;
  latest_outcome_job?: Record<string, unknown> | null;
  calibration_ready: boolean;
}

export interface DataHealthSummary {
  provider_availability?: Record<string, boolean>;
  price_freshness?: Record<string, unknown>;
  missing_stocks?: string[];
  stale_stocks?: string[];
  reconciliation_issues?: string[];
  data_confidence?: Record<string, unknown>;
  excluded_stock_counts?: Record<string, number>;
  integrity_blockers: string[];
}

export interface ResearchJobMonitorItem {
  job_id: string;
  job_name: string;
  status: string;
  stage?: string;
  duration_seconds?: number | null;
  experiment_id?: string | null;
  run_id?: string | null;
  error_message?: string | null;
  error_details?: Record<string, unknown>;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  retry_blocked?: boolean;
}

export interface ModelConfigurationSummary {
  strategy_version: string;
  factor_model_version: string;
  current_regime?: string | null;
  dynamic_weights_enabled: boolean;
  weights_by_sleeve?: Record<string, Record<string, number>>;
  enabled_research_features?: Record<string, boolean>;
  read_only?: boolean;
}

export interface ModelMonitorResponse {
  sleeve: string;
  factor_health: FactorHealthItem[];
  prediction_health: PredictionHealthSummary;
  data_health: DataHealthSummary;
  research_jobs: ResearchJobMonitorItem[];
  model_configuration: ModelConfigurationSummary;
}

export interface MajorEvidenceGateResult {
  passed_checks?: string[];
  failed_checks?: string[];
  warnings?: string[];
  sample_size?: number | null;
  integrity_blockers?: string[];
}

export interface EvidenceReviewFinding {
  finding_id: string;
  source_type: string;
  title: string;
  evidence_impact: string;
  verdict?: string | null;
  sleeve?: string | null;
  symbol?: string | null;
  supporting_run_ids: string[];
  gate?: MajorEvidenceGateResult | null;
  sample_size?: number | null;
  review_required: boolean;
  unresolved_warnings: string[];
  model_versions: Record<string, string>;
  review_history: Array<Record<string, unknown>>;
}

export interface EvidenceReviewListResponse {
  findings: EvidenceReviewFinding[];
  total: number;
}

export interface EvidenceReviewActionResponse {
  finding_id: string;
  action: string;
  evidence_impact: string;
  proposal_id?: string | null;
  audit_id?: number | null;
}

export interface JobRetryResponse {
  job_id: string;
  retried_as?: string | null;
  duplicate_blocked: boolean;
  message: string;
}

