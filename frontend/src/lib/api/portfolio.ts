import type {
  BrokerageCsvImportResponse,
  CsvApproveRequest,
  CsvPreviewResponse,
  DailyDashboardResponse,
  DailyTradingPlanReviewRequest,
  DailyTradingPlanReviewResponse,
  HomeRefreshResponse,
  HomeRefreshStatusResponse,
  LedgerEntry,
  LedgerEntryInput,
  LedgerListResponse,
  PortfolioDecisionRequest,
  PortfolioDecisionResponse,
  PortfolioDecisionRunResponse,
  PortfolioOptimizeRequest,
  PortfolioOptimizeResponse,
  PortfolioPolicyBacktestRequest,
  PortfolioPolicyBacktestResponse,
  PortfolioPerformanceResponse,
  PortfolioSummaryResponse,
  RebalancePreviewRequest,
  RebalancePreviewResponse,
} from "../types";
import { request, resolveApiBaseUrl } from "./client";

export function getPortfolioSummary(): Promise<PortfolioSummaryResponse> {
  return request("/portfolio/summary");
}

export function getPortfolioPerformance(): Promise<PortfolioPerformanceResponse> {
  return request("/portfolio/performance", { timeoutMs: 90_000 });
}

export function getPortfolioRebalancePreview(
  body: RebalancePreviewRequest,
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
  body: PortfolioPolicyBacktestRequest,
): Promise<PortfolioPolicyBacktestResponse> {
  return request("/portfolio/policy-backtest", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function runPortfolioDailyDecision(
  body: PortfolioDecisionRequest,
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

export function getDailyTradingPlanReview(
  tradingDate: string,
): Promise<DailyTradingPlanReviewResponse | null> {
  const qs = `?trading_date=${encodeURIComponent(tradingDate)}`;
  return request(`/portfolio/daily-trading-plan/review${qs}`);
}

export function saveDailyTradingPlanReview(
  body: DailyTradingPlanReviewRequest,
): Promise<DailyTradingPlanReviewResponse> {
  return request("/portfolio/daily-trading-plan/review", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function importRobinhoodCsv(
  file: File,
  cash?: number,
  replace = false,
): Promise<BrokerageCsvImportResponse> {
  const form = new FormData();
  form.append("file", file);
  if (cash != null) form.append("cash", String(cash));
  if (replace) form.append("replace", "true");
  const res = await fetch(`${resolveApiBaseUrl()}/brokerage/import/robinhood-csv`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Import failed: ${res.status}`);
  }
  return res.json() as Promise<BrokerageCsvImportResponse>;
}

export async function previewRobinhoodCsv(file: File, replace = false): Promise<CsvPreviewResponse> {
  const form = new FormData();
  form.append("file", file);
  if (replace) form.append("replace", "true");
  const res = await fetch(`${resolveApiBaseUrl()}/brokerage/preview/robinhood-csv`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Preview failed: ${res.status}`);
  }
  return res.json() as Promise<CsvPreviewResponse>;
}

export async function approveRobinhoodCsv(body: CsvApproveRequest): Promise<BrokerageCsvImportResponse> {
  return request("/brokerage/import/robinhood-csv/approve", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getPortfolioLedger(): Promise<LedgerListResponse> {
  return request("/brokerage/ledger");
}

export function createLedgerEntry(body: LedgerEntryInput): Promise<LedgerEntry> {
  return request("/brokerage/ledger", { method: "POST", body: JSON.stringify(body) });
}

export function updateLedgerEntry(id: number, body: Partial<LedgerEntryInput>): Promise<LedgerEntry> {
  return request(`/brokerage/ledger/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteLedgerEntry(id: number): Promise<{ deleted: boolean; id: number }> {
  return request(`/brokerage/ledger/${id}`, { method: "DELETE" });
}

export function rebuildPortfolioLedger(): Promise<{ holdings_count: number; holdings: unknown[]; cash: number }> {
  return request("/brokerage/ledger/rebuild", { method: "POST" });
}

export type RobinhoodMcpProbeResult = {
  ok: boolean;
  latency_ms: number;
  account_id?: string | null;
  accounts_count?: number;
  holdings_count?: number;
  cash?: number | null;
  equity_value?: number | null;
  portfolio_value?: number | null;
  error?: string | null;
  needs_reauth?: boolean;
  message?: string;
};

export type RobinhoodMcpStatusResponse = {
  enabled: boolean;
  authenticated: boolean;
  endpoint: string;
  login_script?: string;
  sync_script?: string;
  docs_path?: string;
  token_path?: string;
  token_expires_at?: number | null;
  token_expired?: boolean;
  probe?: RobinhoodMcpProbeResult | null;
};

export type RobinhoodMcpSyncResponse = {
  holdings_count?: number;
  holdings?: unknown[];
  cash?: number;
  portfolio_value?: number | null;
  data_source?: string;
  orders_imported?: number;
  orders_skipped?: number;
  ledger_rows_count?: number;
  message?: string;
};

export function getRobinhoodMcpStatus(probe = false): Promise<RobinhoodMcpStatusResponse> {
  const qs = probe ? "?probe=true" : "";
  return request(`/brokerage/robinhood-mcp/status${qs}`, { timeoutMs: probe ? 45_000 : 15_000 });
}

export function testRobinhoodMcpConnection(): Promise<RobinhoodMcpStatusResponse> {
  return request("/brokerage/robinhood-mcp/test", { method: "POST", timeoutMs: 45_000 });
}

export type RobinhoodMcpSyncJobResponse = {
  job_id: string;
  status: "running" | "completed" | "failed";
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  result?: RobinhoodMcpSyncResponse | null;
  message?: string;
};

const MCP_SYNC_POLL_MS = 2000;
/** ~3 minutes — positions+orders sync; decision only runs when holdings > 0. */
const MCP_SYNC_MAX_POLLS = 90;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Soft timeout: sync may still finish in the background; not a hard MCP failure. */
export class RobinhoodMcpSyncTimeoutError extends Error {
  readonly soft = true as const;
  constructor(message: string) {
    super(message);
    this.name = "RobinhoodMcpSyncTimeoutError";
  }
}

export function startRobinhoodMcpSync(runDecision = false): Promise<{ job_id: string; status: string }> {
  const qs = runDecision ? "?run_decision=true" : "";
  return request(`/brokerage/sync/robinhood-mcp${qs}`, { method: "POST", timeoutMs: 30_000 });
}

export function getRobinhoodMcpSyncJob(jobId: string): Promise<RobinhoodMcpSyncJobResponse> {
  return request(`/brokerage/sync/robinhood-mcp/${encodeURIComponent(jobId)}`, { timeoutMs: 15_000 });
}

function jobResultOrEmpty(job: RobinhoodMcpSyncJobResponse): RobinhoodMcpSyncResponse {
  return job.result ?? { message: job.message || "Robinhood portfolio synced." };
}

export async function syncRobinhoodMcp(runDecision = false): Promise<RobinhoodMcpSyncResponse> {
  const start = await startRobinhoodMcpSync(runDecision);
  for (let i = 0; i < MCP_SYNC_MAX_POLLS; i += 1) {
    if (i > 0) {
      await sleep(MCP_SYNC_POLL_MS);
    }
    const job = await getRobinhoodMcpSyncJob(start.job_id);
    // Completed with empty holdings is still success (cash-only) — do not require result fields.
    if (job.status === "completed") {
      return jobResultOrEmpty(job);
    }
    if (job.status === "failed") {
      throw new Error(job.error || "Robinhood sync failed");
    }
  }
  // Final check — sync often finishes just after the poll window.
  const last = await getRobinhoodMcpSyncJob(start.job_id);
  if (last.status === "completed") {
    return jobResultOrEmpty(last);
  }
  if (last.status === "failed") {
    throw new Error(last.error || "Robinhood sync failed");
  }
  throw new RobinhoodMcpSyncTimeoutError(
    "Robinhood sync is still running in the background — refresh Today in a moment. This is not a connection failure.",
  );
}

export async function setBuyingPower(
  cash: number,
  reservedCash = 0,
  ipo?: { shares?: number; listPrice?: number },
): Promise<{ cash: number; reserved_cash: number }> {
  const form = new FormData();
  form.append("cash", String(cash));
  form.append("reserved_cash", String(reservedCash));
  if (ipo?.shares != null && ipo.shares > 0) form.append("ipo_shares", String(ipo.shares));
  if (ipo?.listPrice != null && ipo.listPrice > 0) form.append("ipo_list_price", String(ipo.listPrice));
  const res = await fetch(`${resolveApiBaseUrl()}/brokerage/buying-power`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Update buying power failed: ${res.status}`);
  }
  return res.json() as Promise<{ cash: number; reserved_cash: number }>;
}
