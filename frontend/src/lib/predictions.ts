import type { FeedbackSummaryResponse, PredictionSnapshotItem } from "./types";

export function isPredictionResolved(item: PredictionSnapshotItem): boolean {
  return item.outcome != null;
}

export function predictionDisplayScore(item: PredictionSnapshotItem): number | null {
  if (item.alpha_score != null && Number.isFinite(item.alpha_score)) return item.alpha_score;
  if (item.score != null && Number.isFinite(item.score)) return item.score;
  if (item.confidence != null && Number.isFinite(item.confidence)) return item.confidence;
  return null;
}

export function predictionReturnPct(
  item: PredictionSnapshotItem,
  horizon: 20 | 60 = 60
): number | null {
  if (!item.outcome) return item.realized_return_pct ?? null;
  const key = horizon === 20 ? "return_20d" : "return_60d";
  const value = item.outcome[key];
  return value != null && Number.isFinite(value) ? value : item.realized_return_pct ?? null;
}

export function countUnresolvedPredictions(items: PredictionSnapshotItem[]): number {
  return items.filter((item) => !isPredictionResolved(item)).length;
}

export function countResolvedPredictions(items: PredictionSnapshotItem[]): number {
  return items.filter(isPredictionResolved).length;
}

const DEFAULT_STALE_MS = 7 * 24 * 60 * 60 * 1000;

/** Heuristic: unresolved snapshots older than staleMs with no trade outcomes resolved. */
export function arePredictionOutcomesStale(
  predictions: PredictionSnapshotItem[],
  feedback: FeedbackSummaryResponse | null,
  staleMs = DEFAULT_STALE_MS
): boolean {
  if (feedback?.stale === true) return true;

  const unresolved = predictions.filter((item) => !isPredictionResolved(item));
  if (unresolved.length === 0) return false;

  if (feedback && feedback.snapshots_count > 0 && feedback.outcomes_count === 0) {
    const oldest = Math.min(...unresolved.map((item) => new Date(item.created_at).getTime()));
    if (Number.isFinite(oldest) && Date.now() - oldest > staleMs) return true;
  }

  return false;
}

export function formatScore(value: number | null): string {
  return value != null && Number.isFinite(value) ? value.toFixed(1) : "—";
}
