import { parseApiError } from "@/lib/apiError";
import { getApiBaseUrl, isBackendWakingError } from "@/lib/apiConfig";
import { fmt } from "@/lib/i18n/format";
import type { Messages } from "@/lib/i18n/messages/en";

export function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") return true;
  const msg = error instanceof Error ? error.message : String(error);
  return msg.toLowerCase().includes("abort");
}

function parseDetail(error: unknown, fallback: string): string {
  return parseApiError(error, fallback);
}

function isTimeoutDetail(detail: string): boolean {
  return detail.toLowerCase().includes("timed out");
}

export function explainWorkspaceLoadError(error: unknown, t: Messages): string {
  const detail = parseDetail(error, t.workspace.loadFailed);
  if (isTimeoutDetail(detail)) {
    return fmt(t.workspace.fetchFailedDetail, { detail: t.workspace.fetchFailedTimeout });
  }
  if (isBackendWakingError(detail)) {
    const url = getApiBaseUrl() || t.workspace.fetchFailedNoUrl;
    return fmt(t.workspace.fetchFailedUnreachable, { url });
  }
  return fmt(t.workspace.fetchFailedDetail, { detail });
}

export function explainAnalysisLoadError(error: unknown, t: Messages, symbol: string): string {
  const detail = parseDetail(error, t.analysis.failed);
  if (isTimeoutDetail(detail)) {
    return fmt(t.analysis.fetchFailedTimeout, { symbol });
  }
  if (isBackendWakingError(detail)) {
    const url = getApiBaseUrl() || t.workspace.fetchFailedNoUrl;
    return fmt(t.analysis.fetchFailedUnreachable, { symbol, url });
  }
  return fmt(t.analysis.fetchFailedDetail, { symbol, detail });
}
