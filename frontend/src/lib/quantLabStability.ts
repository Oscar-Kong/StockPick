import { isStaleTimestamp } from "@/lib/quantHealth";
import type { JobLogEntry, WalkForwardResearchResponse } from "@/lib/types";

/** Factor IC older than this is considered stale in Quant Lab. */
export const FACTOR_IC_STALE_MS = 7 * 24 * 60 * 60 * 1000;

const WF_LAST_RUN_KEY = "quant-lab-wf-last-run";

export function isFactorIcStale(asOfDate: string | null | undefined): boolean {
  if (!asOfDate) return true;
  return isStaleTimestamp(`${asOfDate}T12:00:00.000Z`, FACTOR_IC_STALE_MS);
}

export function countFailedSchedulerJobs(jobs: JobLogEntry[] | undefined): number {
  return (jobs ?? []).filter((j) => j.status?.toLowerCase() === "failed").length;
}

export function saveWalkForwardLastRun(result: WalkForwardResearchResponse): void {
  if (typeof window === "undefined" || !result.run_id) return;
  try {
    localStorage.setItem(
      WF_LAST_RUN_KEY,
      JSON.stringify({
        run_id: result.run_id,
        status: result.status,
        periods_scored: result.periods_scored,
        saved_at: new Date().toISOString(),
      })
    );
  } catch {
    // ignore quota / private mode
  }
}

export interface WalkForwardLastRun {
  run_id: string;
  status: string;
  periods_scored: number;
  saved_at: string;
}

export function loadWalkForwardLastRun(): WalkForwardLastRun | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(WF_LAST_RUN_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as WalkForwardLastRun;
    if (!parsed?.run_id) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function validateWalkForwardHorizons(horizons: number[]): string | null {
  if (horizons.length === 0) return "no_horizons";
  if (horizons.some((h) => !Number.isFinite(h) || h < 1 || h > 365)) return "invalid_horizon";
  return null;
}
