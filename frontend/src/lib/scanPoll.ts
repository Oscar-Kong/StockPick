import { getScanStatus } from "@/lib/api";
import { SCAN_STATUS_REQUEST_TIMEOUT_MS } from "@/lib/apiConfig";
import type { ScanStatusResponse } from "@/lib/types";

/** Client-side scan job polling interval. */
export const SCAN_POLL_INTERVAL_MS = 1500;
/** Re-export for tests and callers that need the per-poll HTTP timeout. */
export { SCAN_STATUS_REQUEST_TIMEOUT_MS };
/** Give up only after this many consecutive status-fetch errors (transient blips retry). */
export const SCAN_POLL_MAX_CONSECUTIVE_ERRORS = 20;

export type ScanPollCallbacks = {
  onUpdate: (data: ScanStatusResponse) => void;
  onComplete: (data: ScanStatusResponse) => void;
  onFailed: (reason: string) => void;
};

type GetScanStatusFn = (jobId: string) => Promise<ScanStatusResponse>;

/**
 * Poll a scan job until it completes, fails, or status fetches keep failing.
 * No wall-clock cap — the UI waits for the backend job to finish.
 */
export function startScanPoll(
  jobId: string,
  callbacks: ScanPollCallbacks,
  getStatus: GetScanStatusFn = getScanStatus
): () => void {
  let consecutiveErrors = 0;
  let stopped = false;

  const stop = () => {
    stopped = true;
    clearInterval(interval);
  };

  const interval = setInterval(async () => {
    if (stopped) return;
    try {
      const data = await getStatus(jobId);
      consecutiveErrors = 0;
      callbacks.onUpdate(data);
      if (data.status === "completed") {
        callbacks.onComplete(data);
        stop();
      } else if (data.status === "failed") {
        callbacks.onFailed(data.message?.trim() || "Scan failed");
        stop();
      }
    } catch (err) {
      consecutiveErrors += 1;
      if (consecutiveErrors >= SCAN_POLL_MAX_CONSECUTIVE_ERRORS) {
        const reason =
          err instanceof Error && err.message
            ? err.message
            : "Could not fetch scan status";
        callbacks.onFailed(reason);
        stop();
      }
    }
  }, SCAN_POLL_INTERVAL_MS);

  return stop;
}
