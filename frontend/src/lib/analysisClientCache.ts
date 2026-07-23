/** Small in-memory LRU for Workspace symbol analysis (session-scoped). */

import type { AnalyzeFreshness, AnalyzeSymbolResponse, V2ScoreResponse } from "@/lib/types";

const MAX_ENTRIES = 16;

export type AnalysisCacheEntry = {
  base: AnalyzeSymbolResponse;
  v2?: V2ScoreResponse | null;
  freshness?: AnalyzeFreshness | null;
  savedAt: number;
};

const store = new Map<string, AnalysisCacheEntry>();

export function analysisCacheKey(symbol: string, bucket?: string | null): string {
  return `${symbol.toUpperCase()}:${(bucket || "penny").toLowerCase()}`;
}

export function getAnalysisCache(key: string): AnalysisCacheEntry | null {
  const entry = store.get(key);
  if (!entry) return null;
  // Refresh LRU order
  store.delete(key);
  store.set(key, entry);
  return entry;
}

export function setAnalysisCache(key: string, entry: Omit<AnalysisCacheEntry, "savedAt">): void {
  if (store.has(key)) store.delete(key);
  store.set(key, { ...entry, savedAt: Date.now() });
  while (store.size > MAX_ENTRIES) {
    const oldest = store.keys().next().value;
    if (oldest == null) break;
    store.delete(oldest);
  }
}

export function clearAnalysisCache(key?: string): void {
  if (key) store.delete(key);
  else store.clear();
}
