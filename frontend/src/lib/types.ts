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
}

export interface ScanOptions {
  max_results?: number;
  min_price?: number;
  max_price?: number;
  min_volume?: number;
  exclude_sectors?: string[];
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
  alpha_vantage_configured: boolean;
  fred_configured: boolean;
  newsapi_configured: boolean;
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

export interface V2ScoreResponse {
  symbol: string;
  sleeve: string;
  score: number;
  market_regime?: string | null;
  recommendation?: RecommendationV2 | null;
  valuation?: ValuationV2 | null;
  earnings_setup?: Record<string, unknown>;
  similar_signal?: SimilarSignalV2 | null;
  portfolio_impact?: PortfolioImpactV2 | null;
  position_sizing?: PositionSizingV2 | null;
  prediction_snapshot_id?: number | null;
  summary: string;
  risk_level: string;
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
  long_only?: boolean;
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
