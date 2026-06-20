// API client helpers that wrap backend endpoints for the frontend.
import type {
  AllocationRecommendationResponse,
  AlphaIngestRequest,
  AlphaIngestResponse,
  AlphaLatestResponse,
  PortfolioPolicyBacktestRequest,
  PortfolioPolicyBacktestResponse,
  PortfolioDecisionRequest,
  PortfolioDecisionResponse,
  PortfolioDecisionRunResponse,
  DailyDashboardResponse,
  HomeRefreshResponse,
  HomeRefreshStatusResponse,
  BrokerageCsvImportResponse,
  PortfolioOptimizeRequest,
  PortfolioOptimizeResponse,
  PortfolioSummaryResponse,
  RebalancePreviewRequest,
  RebalancePreviewResponse,
  LeanExportRequest,
  LeanExportResponse,
  LeanImportSummaryRequest,
  LeanImportSummaryResponse,
  BacktestParamOverrides,
  BacktestSweepRequest,
  BacktestSweepResponse,
  BacktestResult,
  Bucket,
  EntryVariantItem,
  ExplainResponse,
  ApiSettingsResponse,
  HealthResponse,
  LatestScanResponse,
  MultiHorizonBacktestResponse,
  ScanJobResponse,
  ScanOptions,
  ScanPickSummaryResponse,
  ScanStatusResponse,
  StockDetail,
  StockResult,
  StockResearchReport,
  PositionSizingV2,
  SymbolDiagnosticsResponse,
  FactorExposureRequest,
  FactorExposureResponse,
  UnifiedRiskV2,
  V2ScoreResponse,
  MarketRegimeV2,
  SleeveWeightsV2,
  HardFiltersResponse,
  FactorPerformanceResponse,
  PredictionsListResponse,
  FeedbackSummaryResponse,
  WalkForwardResearchRequest,
  WalkForwardResearchResponse,
  WalkForwardRunDetailResponse,
  QuantLabLastRunSummary,
  QuantLabEvidenceResponse,
  PairsResearchRequest,
  PairsResearchResponse,
  SchedulerStatusResponse,
  V2VersionResponse,
  V2AuditResponse,
  V2FactorsAdminResponse,
  V2JobsQueueResponse,
  SimilarSignalBacktestResponse,
  ValuationV2,
  QuantHealthSummary,
  QuantHealthSection,
  SavedReportCreateRequest,
  SavedAnalyzeItem,
  SavedProgressSummary,
  SavedReportItem,
  SavedReportUpdateRequest,
  SavedScanCreateRequest,
  SavedScanItem,
  TradeCreateRequest,
  TradeManualResponse,
  TraderPresetResponse,
  TraderProfileListResponse,
  TraderQuickCompareResponse,
  TradeItem,
  TradeStatsResponse,
  WatchlistImportRequest,
  WatchlistImportResponse,
  WatchlistItem,
  WatchlistRefreshResponse,
  AnalyzeSymbolResponse,
  AnalyzeWatchlistResponse,
} from "./types";
import type { Locale } from "@/lib/i18n";
import { normalizeLastRunSummary, normalizeQuantLabEvidence } from "./quantLabLastRun";
import {
  getApiBaseUrl,
  HEALTH_CHECK_TIMEOUT_MS,
  HEALTH_RETRY_ATTEMPTS,
  HEALTH_RETRY_DELAY_MS,
  isBackendWakingError,
  SCAN_REQUEST_TIMEOUT_MS,
  SCAN_STATUS_REQUEST_TIMEOUT_MS,
  WALK_FORWARD_REQUEST_TIMEOUT_MS,
  PAIRS_RESEARCH_REQUEST_TIMEOUT_MS,
} from "./apiConfig";
import { parseApiError } from "./apiError";
import {
  normalizeFactorPerformanceResponse,
  normalizeFeedbackSummaryResponse,
  normalizePairsResearchResponse,
  normalizePredictionsListResponse,
  normalizeSchedulerStatusResponse,
  normalizeV2AuditResponse,
  normalizeV2FactorsAdminResponse,
  normalizeWalkForwardResearchResponse,
} from "./quantLabNormalizers";

const API_URL = getApiBaseUrl();

const DEFAULT_REQUEST_TIMEOUT_MS = 45_000;
const ANALYZE_REQUEST_TIMEOUT_MS = 40_000;

async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, signal: callerSignal, ...rest } = init ?? {};
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  if (callerSignal) {
    if (callerSignal.aborted) {
      controller.abort();
    } else {
      callerSignal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }

  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...rest.headers,
      },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(parseApiError(new Error(text || `Request failed: ${res.status}`)));
    }
    return res.json() as Promise<T>;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function startScan(bucket: Bucket, options?: ScanOptions): Promise<ScanJobResponse> {
  return request(`/scan/${bucket}`, {
    method: "POST",
    body: JSON.stringify(options ?? {}),
    timeoutMs: SCAN_REQUEST_TIMEOUT_MS,
  });
}

export function getScanStatus(jobId: string): Promise<ScanStatusResponse> {
  return request(`/scan/${jobId}`, {
    timeoutMs: SCAN_STATUS_REQUEST_TIMEOUT_MS,
  });
}

export function getLatestScan(bucket: Bucket): Promise<LatestScanResponse> {
  return request(`/scan/latest/${bucket}`);
}

export function getScanPickSummary(
  bucket: Bucket,
  stock: StockResult,
  locale: Locale = "en"
): Promise<ScanPickSummaryResponse> {
  return request(`/scan/${bucket}/${stock.symbol}/pick-summary`, {
    method: "POST",
    body: JSON.stringify({
      score: stock.score,
      summary: stock.summary,
      signals: stock.signals,
      metrics: stock.metrics ?? {},
      locale,
    }),
  });
}

export function listSavedScans(bucket?: Bucket): Promise<SavedScanItem[]> {
  const qs = bucket ? `?bucket=${bucket}` : "";
  return request(`/saved/scans${qs}`);
}

export function saveScanSnapshot(body: SavedScanCreateRequest): Promise<SavedScanItem> {
  return request("/saved/scans", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteSavedScan(scanId: number): Promise<{ ok: boolean }> {
  return request(`/saved/scans/${scanId}`, { method: "DELETE" });
}

export function getStock(
  symbol: string,
  bucket?: Bucket,
  includeBacktest = false
): Promise<StockDetail> {
  const params = new URLSearchParams();
  if (bucket) params.set("bucket", bucket);
  if (includeBacktest) params.set("include_backtest", "true");
  const qs = params.toString() ? `?${params}` : "";
  return request(`/stock/${symbol}${qs}`);
}

export function getBacktest(
  bucket: Bucket,
  symbol: string,
  horizon = "3y",
  multiHorizon = false,
  engine: "default" | "vectorbt" = "default",
  overrides?: BacktestParamOverrides
): Promise<BacktestResult | MultiHorizonBacktestResponse> {
  const params = new URLSearchParams({
    horizon,
    multi_horizon: String(multiHorizon),
    engine,
  });
  if (overrides?.hold_days != null) params.set("hold_days", String(overrides.hold_days));
  if (overrides?.stop_pct != null) params.set("stop_pct", String(overrides.stop_pct));
  if (overrides?.target_pct != null) params.set("target_pct", String(overrides.target_pct));
  if (overrides?.entry_variant) params.set("entry_variant", overrides.entry_variant);
  return request(`/backtest/${bucket}/${symbol}?${params}`);
}

export function listEntryVariants(bucket: Bucket): Promise<{ bucket: Bucket; variants: EntryVariantItem[] }> {
  return request(`/backtest/entry-variants/${bucket}`);
}

export function runBacktestSweep(
  bucket: Bucket,
  symbol: string,
  body: BacktestSweepRequest,
  engine: "default" | "vectorbt" = "default"
): Promise<BacktestSweepResponse> {
  return request(`/backtest/${bucket}/${symbol}/sweep?engine=${engine}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getPortfolioSummary(): Promise<PortfolioSummaryResponse> {
  return request("/portfolio/summary");
}

export function getPortfolioRebalancePreview(
  body: RebalancePreviewRequest
): Promise<RebalancePreviewResponse> {
  return request("/portfolio/rebalance-preview", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function optimizePortfolio(body: PortfolioOptimizeRequest): Promise<PortfolioOptimizeResponse> {
  return request("/portfolio/optimize", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function runPortfolioPolicyBacktest(
  body: PortfolioPolicyBacktestRequest
): Promise<PortfolioPolicyBacktestResponse> {
  return request("/portfolio/policy-backtest", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function runPortfolioDailyDecision(
  body: PortfolioDecisionRequest
): Promise<PortfolioDecisionResponse> {
  return request("/portfolio/daily-decision", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getDailyDashboard(opts?: { skipAutoRefresh?: boolean }): Promise<DailyDashboardResponse> {
  const qs = opts?.skipAutoRefresh ? "?skip_auto_refresh=true" : "";
  return request(`/home/daily-dashboard${qs}`);
}

export function refreshHomeData(force = false): Promise<HomeRefreshResponse> {
  return request(`/home/refresh?force=${force ? "true" : "false"}`, { method: "POST" });
}

export function getHomeRefreshStatus(jobId: string): Promise<HomeRefreshStatusResponse> {
  return request(`/home/refresh-status/${encodeURIComponent(jobId)}`);
}

export function runDailyDecisionNow(): Promise<PortfolioDecisionRunResponse> {
  return request("/portfolio/daily-decision/run", { method: "POST" });
}

export async function importRobinhoodCsv(
  file: File,
  cash?: number,
  replace = false
): Promise<BrokerageCsvImportResponse> {
  const form = new FormData();
  form.append("file", file);
  if (cash != null) form.append("cash", String(cash));
  if (replace) form.append("replace", "true");
  const res = await fetch(`${API_URL}/brokerage/import/robinhood-csv`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Import failed: ${res.status}`);
  }
  return res.json() as Promise<BrokerageCsvImportResponse>;
}

export async function setBuyingPower(
  cash: number,
  reservedCash = 0,
  ipo?: { shares?: number; listPrice?: number }
): Promise<{ cash: number; reserved_cash: number }> {
  const form = new FormData();
  form.append("cash", String(cash));
  form.append("reserved_cash", String(reservedCash));
  if (ipo?.shares != null && ipo.shares > 0) form.append("ipo_shares", String(ipo.shares));
  if (ipo?.listPrice != null && ipo.listPrice > 0) form.append("ipo_list_price", String(ipo.listPrice));
  const res = await fetch(`${API_URL}/brokerage/buying-power`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Update buying power failed: ${res.status}`);
  }
  return res.json() as Promise<{ cash: number; reserved_cash: number }>;
}

export function runV2PortfolioBacktest(
  body: PortfolioPolicyBacktestRequest
): Promise<PortfolioPolicyBacktestResponse> {
  return request("/api/v2/backtest/portfolio", {
    method: "POST",
    body: JSON.stringify({ ...body, institutional: true }),
  });
}

export function getLatestAlpha(bucket: Bucket = "penny"): Promise<AlphaLatestResponse> {
  return request(`/ml/alpha/latest?bucket=${bucket}`);
}

export function ingestAlphaPredictions(body: AlphaIngestRequest): Promise<AlphaIngestResponse> {
  return request("/ml/alpha/ingest", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getAllocationRecommendation(
  bucket: Bucket,
  symbols?: string[]
): Promise<AllocationRecommendationResponse> {
  const qs = symbols && symbols.length ? `?symbols=${symbols.join(",")}` : "";
  return request(`/allocation/recommendation/${bucket}${qs}`);
}

export function exportToLean(body: LeanExportRequest): Promise<LeanExportResponse> {
  return request("/lean/export", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getLeanExport(exportId: string): Promise<Record<string, unknown>> {
  return request(`/lean/export/${exportId}`);
}

export function importLeanSummary(
  body: LeanImportSummaryRequest
): Promise<LeanImportSummaryResponse> {
  return request("/lean/import-summary", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function explainStock(symbol: string, bucket: Bucket): Promise<ExplainResponse> {
  return request("/explain", {
    method: "POST",
    body: JSON.stringify({ symbol, bucket }),
  });
}

export function getHealth(): Promise<HealthResponse> {
  return request("/health", { timeoutMs: HEALTH_CHECK_TIMEOUT_MS });
}

export async function getHealthWithRetry(): Promise<HealthResponse> {
  let lastError: unknown;
  for (let attempt = 0; attempt < HEALTH_RETRY_ATTEMPTS; attempt += 1) {
    try {
      return await getHealth();
    } catch (err) {
      lastError = err;
      if (attempt < HEALTH_RETRY_ATTEMPTS - 1) {
        await new Promise((resolve) => setTimeout(resolve, HEALTH_RETRY_DELAY_MS));
      }
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Backend health check failed");
}

export function isApiWakingError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return isBackendWakingError(parseApiError(error));
}

export function getApiSettings(): Promise<ApiSettingsResponse> {
  return request("/settings/apis");
}

export function patchApiSettings(updates: Record<string, boolean>): Promise<ApiSettingsResponse> {
  return request("/settings/apis", {
    method: "PATCH",
    body: JSON.stringify({ updates }),
  });
}

export function resetApiSettings(keys?: string[]): Promise<ApiSettingsResponse> {
  return request("/settings/apis/reset", {
    method: "POST",
    body: JSON.stringify(keys?.length ? { keys } : {}),
  });
}

export function getWatchlist(): Promise<WatchlistItem[]> {
  return request("/watchlist");
}

export function addToWatchlist(
  symbol: string,
  bucket: Bucket,
  notes = ""
): Promise<WatchlistItem> {
  return request("/watchlist", {
    method: "POST",
    body: JSON.stringify({ symbol, bucket, notes }),
  });
}

export function removeFromWatchlist(symbol: string): Promise<{ ok: boolean }> {
  return request(`/watchlist/${symbol}`, { method: "DELETE" });
}

export function refreshWatchlist(): Promise<WatchlistRefreshResponse> {
  return request("/watchlist/refresh", { method: "POST" });
}

export function importWatchlist(
  body: WatchlistImportRequest
): Promise<WatchlistImportResponse> {
  return request("/watchlist/import", {
    method: "POST",
    body: JSON.stringify({
      input: body.input,
      bucket: body.bucket ?? "auto",
      notes: body.notes ?? "",
    }),
  });
}

export function getAnalyzeWatchlist(): Promise<AnalyzeWatchlistResponse> {
  return request("/analyze/watchlist");
}

export type AnalyzeSymbolOptions = {
  signal?: AbortSignal;
  refresh?: boolean;
  includeBucketFit?: boolean;
};

export function getAnalyzeSymbol(
  symbol: string,
  bucket?: Bucket,
  options?: AnalyzeSymbolOptions
): Promise<AnalyzeSymbolResponse> {
  const params = new URLSearchParams();
  if (bucket) params.set("bucket", bucket);
  if (options?.refresh) params.set("refresh", "1");
  if (options?.includeBucketFit) params.set("include_bucket_fit", "1");
  const qs = params.toString();
  return request(`/analyze/${symbol}${qs ? `?${qs}` : ""}`, {
    signal: options?.signal,
    timeoutMs: ANALYZE_REQUEST_TIMEOUT_MS,
  });
}

export function getAnalyzeBucketFit(
  symbol: string,
  options?: { signal?: AbortSignal }
): Promise<AnalyzeSymbolResponse["bucket_fit"]> {
  return request(`/analyze/${symbol}/bucket-fit`, {
    signal: options?.signal,
    timeoutMs: ANALYZE_REQUEST_TIMEOUT_MS,
  });
}

export function getDataQuality(symbol: string) {
  return request<{
    symbol: string;
    quality_score: number;
    reconcile: { fields?: { field: string; value: number | null; confidence: string }[] };
  }>(`/data/quality/${symbol}`);
}

export function getResearchReport(
  symbol: string,
  bucket?: Bucket
): Promise<StockResearchReport> {
  const qs = bucket ? `?bucket=${bucket}` : "";
  return request(`/analyze/${symbol}/report${qs}`);
}

export function listSavedReports(symbol?: string): Promise<SavedReportItem[]> {
  const qs = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
  return request(`/saved/reports${qs}`);
}

export function saveReportSnapshot(body: SavedReportCreateRequest): Promise<SavedReportItem> {
  return request("/saved/reports", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateSavedReport(
  reportId: number,
  body: SavedReportUpdateRequest
): Promise<SavedReportItem> {
  return request(`/saved/reports/${reportId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteSavedReport(reportId: number): Promise<{ ok: boolean }> {
  return request(`/saved/reports/${reportId}`, { method: "DELETE" });
}

export function listSavedAnalyze(symbol?: string, bucket?: Bucket): Promise<SavedAnalyzeItem[]> {
  const params = new URLSearchParams();
  if (symbol) params.set("symbol", symbol);
  if (bucket) params.set("bucket", bucket);
  const qs = params.toString();
  return request(`/saved/analyze${qs ? `?${qs}` : ""}`);
}

export function getLatestSavedAnalyze(
  symbol: string,
  bucket?: Bucket
): Promise<SavedAnalyzeItem> {
  const qs = bucket ? `?bucket=${bucket}` : "";
  return request(`/saved/analyze/latest/${encodeURIComponent(symbol)}${qs}`);
}

export function getSavedProgressSummary(): Promise<SavedProgressSummary> {
  return request("/saved/progress-summary");
}

export function listTraderIntelProfiles(): Promise<TraderProfileListResponse> {
  return request("/trader-intel");
}

export function getTraderPreset(slug: string, bucket: Bucket): Promise<TraderPresetResponse> {
  return request(`/trader-intel/${encodeURIComponent(slug)}/preset/${bucket}`);
}

export function getTraderQuickCompare(
  slug: string,
  bucket: Bucket
): Promise<TraderQuickCompareResponse> {
  return request(`/trader-intel/${encodeURIComponent(slug)}/quick-compare/${bucket}`);
}

export function updateWatchlistNotes(
  symbol: string,
  notes: string
): Promise<WatchlistItem> {
  return request(`/watchlist/${symbol}/notes`, {
    method: "PATCH",
    body: JSON.stringify({ notes }),
  });
}

export function listTrades(symbol?: string): Promise<TradeItem[]> {
  const qs = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
  return request(`/trades${qs}`);
}

export function createTradeManual(body: TradeCreateRequest): Promise<TradeManualResponse> {
  return request("/trades/manual", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function syncTradeToPortfolio(tradeId: number): Promise<TradeManualResponse> {
  return request(`/trades/${tradeId}/sync-portfolio`, { method: "POST" });
}

export async function createTradeUpload(body: FormData): Promise<TradeManualResponse> {
  const res = await fetch(`${API_URL}/trades/upload`, {
    method: "POST",
    body,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<TradeManualResponse>;
}

export function deleteTrade(tradeId: number): Promise<{ ok: boolean }> {
  return request(`/trades/${tradeId}`, { method: "DELETE" });
}

export function getTradeStats(): Promise<TradeStatsResponse> {
  return request("/trades/stats/summary");
}

export function getSymbolDiagnostics(
  symbol: string,
  lookback = 252,
  options?: { signal?: AbortSignal }
): Promise<SymbolDiagnosticsResponse> {
  const params = new URLSearchParams({ lookback: String(lookback) });
  return request(`/analyze/${encodeURIComponent(symbol)}/diagnostics?${params}`, {
    signal: options?.signal,
  });
}

export function getPortfolioFactorExposure(
  body: FactorExposureRequest
): Promise<FactorExposureResponse> {
  return request("/portfolio/factor-exposure", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getV2Score(
  symbol: string,
  bucket?: Bucket,
  options?: { signal?: AbortSignal }
): Promise<V2ScoreResponse> {
  const qs = bucket ? `?sleeve=${bucket}` : "";
  return request(`/api/v2/score/${symbol}${qs}`, { signal: options?.signal });
}

export function getV2PositionSizing(
  symbol: string,
  bucket?: Bucket,
  options?: { portfolioExposure?: number; signal?: AbortSignal }
): Promise<PositionSizingV2> {
  const params = new URLSearchParams();
  if (bucket) params.set("sleeve", bucket);
  if (options?.portfolioExposure != null) {
    params.set("portfolio_exposure", String(options.portfolioExposure));
  }
  const qs = params.toString() ? `?${params}` : "";
  return request(`/api/v2/sizing/${symbol}${qs}`, { signal: options?.signal });
}

export function getV2UnifiedRisk(
  symbol: string,
  bucket?: Bucket,
  options?: { signal?: AbortSignal }
): Promise<UnifiedRiskV2> {
  const qs = bucket ? `?sleeve=${bucket}` : "";
  return request(`/api/v2/risk/${symbol}${qs}`, { signal: options?.signal });
}

export type V2RequestOptions = { signal?: AbortSignal };

export function getV2Regime(
  refresh = false,
  options?: V2RequestOptions
): Promise<MarketRegimeV2> {
  const qs = refresh ? "?refresh=true" : "";
  return request(`/api/v2/regime${qs}`, { signal: options?.signal });
}

export function getV2SleeveWeights(
  sleeve: Bucket,
  regime?: string,
  options?: V2RequestOptions
): Promise<SleeveWeightsV2> {
  const params = new URLSearchParams();
  if (regime) params.set("regime", regime);
  const qs = params.toString() ? `?${params}` : "";
  return request(`/api/v2/weights/${sleeve}${qs}`, { signal: options?.signal });
}

export function getV2HardFilters(
  sleeve: Bucket,
  options?: V2RequestOptions
): Promise<HardFiltersResponse> {
  return request(`/api/v2/hard-filters/${sleeve}`, { signal: options?.signal });
}

export async function getV2FactorPerformance(
  params?: { sleeve?: Bucket; factorId?: string; horizonDays?: number },
  options?: V2RequestOptions
): Promise<FactorPerformanceResponse> {
  const search = new URLSearchParams();
  if (params?.sleeve) search.set("sleeve", params.sleeve);
  if (params?.factorId) search.set("factor_id", params.factorId);
  if (params?.horizonDays != null) search.set("horizon_days", String(params.horizonDays));
  const qs = search.toString() ? `?${search}` : "";
  const raw = await request<unknown>(`/api/v2/factors/performance${qs}`, { signal: options?.signal });
  return normalizeFactorPerformanceResponse(raw);
}

export async function getV2FactorIc(
  params?: { sleeve?: Bucket; factorId?: string; horizonDays?: number },
  options?: V2RequestOptions
): Promise<FactorPerformanceResponse> {
  const search = new URLSearchParams();
  if (params?.sleeve) search.set("sleeve", params.sleeve);
  if (params?.factorId) search.set("factor_id", params.factorId);
  if (params?.horizonDays != null) search.set("horizon_days", String(params.horizonDays));
  const qs = search.toString() ? `?${search}` : "";
  const raw = await request<unknown>(`/api/v2/factors/ic${qs}`, { signal: options?.signal });
  return normalizeFactorPerformanceResponse(raw);
}

export async function getV2Predictions(
  params?: {
    symbol?: string;
    source?: string;
    sleeve?: Bucket;
    fromDate?: string;
    toDate?: string;
    limit?: number;
  },
  options?: V2RequestOptions
): Promise<PredictionsListResponse> {
  const search = new URLSearchParams();
  if (params?.symbol) search.set("symbol", params.symbol);
  if (params?.source) search.set("source", params.source);
  if (params?.sleeve) search.set("sleeve", params.sleeve);
  if (params?.fromDate) search.set("from_date", params.fromDate);
  if (params?.toDate) search.set("to_date", params.toDate);
  if (params?.limit != null) search.set("limit", String(params.limit));
  const qs = search.toString() ? `?${search}` : "";
  const raw = await request<unknown>(`/api/v2/predictions${qs}`, { signal: options?.signal });
  return normalizePredictionsListResponse(raw);
}

export async function getV2FeedbackSummary(options?: V2RequestOptions): Promise<FeedbackSummaryResponse> {
  const raw = await request<unknown>("/api/v2/feedback/summary", { signal: options?.signal });
  return normalizeFeedbackSummaryResponse(raw);
}

export function getV2Valuation(
  symbol: string,
  options?: V2RequestOptions
): Promise<ValuationV2> {
  return request(`/api/v2/valuation/${encodeURIComponent(symbol)}`, { signal: options?.signal });
}

export function getV2SimilarSignal(
  symbol: string,
  bucket?: Bucket,
  options?: V2RequestOptions
): Promise<SimilarSignalBacktestResponse> {
  const qs = bucket ? `?sleeve=${bucket}` : "";
  return request(`/api/v2/similar-signal/${encodeURIComponent(symbol)}${qs}`, {
    signal: options?.signal,
  });
}

export function getV2Agents(
  symbol: string,
  bucket?: Bucket,
  options?: V2RequestOptions
): Promise<Record<string, unknown>> {
  const qs = bucket ? `?sleeve=${bucket}` : "";
  return request(`/api/v2/agents/${encodeURIComponent(symbol)}${qs}`, { signal: options?.signal });
}

export function getV2Version(options?: V2RequestOptions): Promise<V2VersionResponse> {
  return request("/api/v2/version", { signal: options?.signal });
}

export async function getV2Audit(
  params?: { limit?: number; eventType?: string; symbol?: string },
  options?: V2RequestOptions
): Promise<V2AuditResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.eventType) search.set("event_type", params.eventType);
  if (params?.symbol) search.set("symbol", params.symbol);
  const qs = search.toString() ? `?${search}` : "";
  const raw = await request<unknown>(`/api/v2/audit${qs}`, { signal: options?.signal });
  return normalizeV2AuditResponse(raw);
}

export function getV2JobsQueue(
  limit = 20,
  options?: V2RequestOptions
): Promise<V2JobsQueueResponse> {
  return request(`/api/v2/jobs/queue?limit=${limit}`, { signal: options?.signal });
}

export function getV2Round2Stats(options?: V2RequestOptions): Promise<Record<string, unknown>> {
  return request("/api/v2/admin/round2-stats", { signal: options?.signal });
}

export async function getV2FactorsAdmin(
  sleeve?: Bucket,
  options?: V2RequestOptions
): Promise<V2FactorsAdminResponse> {
  const qs = sleeve ? `?sleeve=${sleeve}` : "";
  const raw = await request<unknown>(`/api/v2/factors/admin${qs}`, { signal: options?.signal });
  return normalizeV2FactorsAdminResponse(raw);
}

export async function runWalkForwardResearch(
  body: WalkForwardResearchRequest,
  options?: V2RequestOptions
): Promise<WalkForwardResearchResponse> {
  const raw = await request<unknown>("/research/walk-forward", {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
    timeoutMs: WALK_FORWARD_REQUEST_TIMEOUT_MS,
  });
  return normalizeWalkForwardResearchResponse(raw);
}

export async function getWalkForwardLatest(
  sleeve: Bucket = "penny",
  options?: V2RequestOptions
): Promise<QuantLabLastRunSummary> {
  const raw = await request<unknown>(`/research/walk-forward/latest?sleeve=${sleeve}`, {
    signal: options?.signal,
  });
  return normalizeLastRunSummary(raw, "walk_forward");
}

export function getWalkForwardRun(
  runId: string,
  options?: V2RequestOptions
): Promise<WalkForwardRunDetailResponse> {
  return request(`/research/walk-forward/${encodeURIComponent(runId)}`, {
    signal: options?.signal,
  });
}

export async function runPairsResearch(
  body: PairsResearchRequest,
  options?: V2RequestOptions
): Promise<PairsResearchResponse> {
  const raw = await request<unknown>("/research/pairs", {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
    timeoutMs: PAIRS_RESEARCH_REQUEST_TIMEOUT_MS,
  });
  return normalizePairsResearchResponse(raw);
}

export async function getPairsLatest(options?: V2RequestOptions): Promise<QuantLabLastRunSummary> {
  const raw = await request<unknown>("/research/pairs/latest", { signal: options?.signal });
  return normalizeLastRunSummary(raw, "pairs");
}

export async function getPairsRun(
  runId: string,
  options?: V2RequestOptions
): Promise<PairsResearchResponse> {
  const raw = await request<unknown>(`/research/pairs/${runId}`, { signal: options?.signal });
  const summary = (raw as { summary?: Record<string, unknown> }).summary ?? raw;
  const pairs = (raw as { pairs?: unknown[] }).pairs ?? [];
  return normalizePairsResearchResponse({ ...(summary as object), pairs, run_id: runId });
}

export async function getQuantLabEvidence(
  sleeve: Bucket = "penny",
  options?: V2RequestOptions
): Promise<QuantLabEvidenceResponse> {
  const raw = await request<unknown>(`/api/v2/quant-lab/evidence?sleeve=${sleeve}`, {
    signal: options?.signal,
  });
  return normalizeQuantLabEvidence(raw);
}

export async function getSchedulerStatus(options?: V2RequestOptions): Promise<SchedulerStatusResponse> {
  const raw = await request<unknown>("/data/scheduler/status", { signal: options?.signal });
  return normalizeSchedulerStatusResponse(raw);
}

export function runSchedulerDailyPipeline(
  options?: V2RequestOptions
): Promise<Record<string, unknown>> {
  return request("/data/scheduler/run", { method: "POST", signal: options?.signal });
}

export function refreshSchedulerQuotes(options?: V2RequestOptions): Promise<Record<string, unknown>> {
  return request("/data/scheduler/refresh-quotes", { method: "POST", signal: options?.signal });
}

export function refreshSchedulerFundamentals(
  options?: V2RequestOptions
): Promise<Record<string, unknown>> {
  return request("/data/scheduler/refresh-fundamentals", {
    method: "POST",
    signal: options?.signal,
  });
}

export function enqueueV2Job(
  jobName: string,
  forceRebalance = false,
  options?: V2RequestOptions
): Promise<Record<string, unknown>> {
  const qs = forceRebalance ? "?force_rebalance=true" : "";
  return request(`/api/v2/jobs/enqueue/${encodeURIComponent(jobName)}${qs}`, {
    method: "POST",
    signal: options?.signal,
  });
}

const STALE_SCAN_MS = 1000 * 60 * 60 * 24;

function scanAgeSeverity(completedAt: string | null | undefined): QuantHealthSection | null {
  if (!completedAt) {
    return {
      id: "scan_freshness",
      label: "Scan freshness",
      severity: "warning",
      message: "No completed scan timestamp",
    };
  }
  const ageMs = Date.now() - new Date(completedAt).getTime();
  if (Number.isNaN(ageMs)) return null;
  const stale = ageMs > STALE_SCAN_MS;
  return {
    id: "scan_freshness",
    label: "Scan freshness",
    severity: stale ? "warning" : "ok",
    message: stale ? "Latest cached scan is older than 24h" : "Latest scan is fresh",
    as_of: completedAt,
  };
}

/** Client-side aggregate until a dedicated /api/v2/health/quant endpoint exists. */
export async function getQuantHealthSummary(
  options?: V2RequestOptions
): Promise<QuantHealthSummary> {
  const checkedAt = new Date().toISOString();
  const sections: QuantHealthSection[] = [];

  const [health, progress, penny, compounder, scheduler, factorPerf] =
    await Promise.allSettled([
      getHealth(),
      getSavedProgressSummary(),
      getLatestScan("penny"),
      getLatestScan("compounder"),
      getSchedulerStatus(options),
      getV2FactorPerformance(undefined, options),
    ]);

  let healthData: HealthResponse | null = null;
  if (health.status === "fulfilled") {
    healthData = health.value;
    const missingProviders = [
      !healthData.fmp_configured && "FMP",
      !healthData.finnhub_configured && "Finnhub",
      !healthData.llm_configured && "LLM",
    ].filter(Boolean) as string[];
    sections.push({
      id: "providers",
      label: "Data providers",
      severity: missingProviders.length >= 2 ? "warning" : "ok",
      message:
        missingProviders.length > 0
          ? `Some providers not configured: ${missingProviders.join(", ")}`
          : "Core providers configured",
    });
    if (!healthData.scheduler_enabled) {
      sections.push({
        id: "scheduler",
        label: "Scheduler",
        severity: "warning",
        message: "Scheduler disabled in environment",
      });
    }
  } else {
    sections.push({
      id: "health",
      label: "System health",
      severity: "error",
      message: "Could not reach /health",
      detail: health.reason instanceof Error ? health.reason.message : String(health.reason),
    });
  }

  const latestScans: Partial<Record<Bucket, LatestScanResponse | null>> = {};
  for (const [bucket, result] of [
    ["penny", penny],
    ["compounder", compounder],
  ] as const) {
    if (result.status === "fulfilled") {
      latestScans[bucket] = result.value;
      const scanSection = scanAgeSeverity(result.value.completed_at);
      if (scanSection && bucket === "penny") {
        sections.push({ ...scanSection, id: `scan_${bucket}` });
      }
    }
  }

  let factorIcAsOf: string | null = null;
  if (factorPerf.status === "fulfilled") {
    factorIcAsOf = factorPerf.value.as_of_date;
    sections.push({
      id: "factor_ic",
      label: "Factor IC",
      severity: factorIcAsOf ? "ok" : "warning",
      message: factorIcAsOf ? `IC panel as of ${factorIcAsOf}` : "No factor IC history yet",
      as_of: factorIcAsOf,
    });
  }

  if (scheduler.status === "fulfilled") {
    const failed = scheduler.value.recent_jobs?.filter((j) => j.status === "failed") ?? [];
    if (failed.length > 0) {
      sections.push({
        id: "scheduler_jobs",
        label: "Scheduler jobs",
        severity: "warning",
        message: `${failed.length} recent job failure(s)`,
        detail: failed[0]?.message ?? null,
      });
    }
  }

  const overall: QuantHealthSummary["overall"] = sections.some((s) => s.severity === "error")
    ? "error"
    : sections.some((s) => s.severity === "warning")
      ? "warning"
      : "ok";

  return {
    overall,
    checked_at: checkedAt,
    sections,
    health: healthData,
    latest_scans: latestScans,
    progress: progress.status === "fulfilled" ? progress.value : null,
    factor_ic_as_of: factorIcAsOf,
  };
}
