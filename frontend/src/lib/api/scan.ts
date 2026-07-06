import type {
  BacktestParamOverrides,
  BacktestResult,
  BacktestSweepRequest,
  BacktestSweepResponse,
  Bucket,
  EntryVariantItem,
  LatestScanResponse,
  MultiHorizonBacktestResponse,
  ScanJobResponse,
  ScanOptions,
  ScanPickSummaryResponse,
  ScanStatusResponse,
  SavedScanCreateRequest,
  SavedScanItem,
  StockDetail,
  StockResult,
} from "../types";
import type { Locale } from "@/lib/i18n";
import { SCAN_REQUEST_TIMEOUT_MS, SCAN_STATUS_REQUEST_TIMEOUT_MS } from "../apiConfig";
import { request } from "./client";

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
  locale: Locale = "en",
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
  includeBacktest = false,
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
  overrides?: BacktestParamOverrides,
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
  engine: "default" | "vectorbt" = "default",
): Promise<BacktestSweepResponse> {
  return request(`/backtest/${bucket}/${symbol}/sweep?engine=${engine}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
