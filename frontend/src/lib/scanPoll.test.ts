import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ScanStatusResponse } from "@/lib/types";
import {
  SCAN_POLL_INTERVAL_MS,
  SCAN_POLL_MAX_CONSECUTIVE_ERRORS,
  startScanPoll,
} from "./scanPoll";

function status(partial: Partial<ScanStatusResponse> & Pick<ScanStatusResponse, "status">): ScanStatusResponse {
  return {
    job_id: "job-1",
    bucket: "penny",
    progress: partial.progress ?? 0,
    message: partial.message ?? "",
    results: partial.results ?? [],
    completed_at: partial.completed_at ?? null,
    ...partial,
  };
}

describe("startScanPoll", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls until completed without a tick cap", async () => {
    const getStatus = vi
      .fn<(jobId: string) => Promise<ScanStatusResponse>>()
      .mockResolvedValueOnce(status({ status: "running", progress: 10, message: "Working" }))
      .mockResolvedValueOnce(
        status({ status: "completed", progress: 100, message: "Done", results: [], completed_at: "2026-01-01" })
      );
    const onComplete = vi.fn();
    const stop = startScanPoll("job-1", { onUpdate: vi.fn(), onComplete, onFailed: vi.fn() }, getStatus);

    await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS);
    await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS);

    expect(getStatus).toHaveBeenCalledTimes(2);
    expect(onComplete).toHaveBeenCalledOnce();
    stop();
  });

  it("surfaces backend failure reason", async () => {
    const getStatus = vi
      .fn<(jobId: string) => Promise<ScanStatusResponse>>()
      .mockResolvedValueOnce(status({ status: "failed", message: "Provider rate limited" }));
    const onFailed = vi.fn();
    startScanPoll("job-1", { onUpdate: vi.fn(), onComplete: vi.fn(), onFailed }, getStatus);

    await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS);

    expect(onFailed).toHaveBeenCalledWith("Provider rate limited");
  });

  it("retries transient fetch errors before giving up", async () => {
    const getStatus = vi
      .fn<(jobId: string) => Promise<ScanStatusResponse>>()
      .mockRejectedValueOnce(new Error("network blip"))
      .mockResolvedValueOnce(status({ status: "completed", progress: 100, message: "Done" }));
    const onComplete = vi.fn();
    const onFailed = vi.fn();
    startScanPoll("job-1", { onUpdate: vi.fn(), onComplete, onFailed }, getStatus);

    await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS);
    await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS);

    expect(onFailed).not.toHaveBeenCalled();
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("fails after consecutive status-fetch errors", async () => {
    const getStatus = vi
      .fn<(jobId: string) => Promise<ScanStatusResponse>>()
      .mockRejectedValue(new Error("API offline"));
    const onFailed = vi.fn();
    startScanPoll("job-1", { onUpdate: vi.fn(), onComplete: vi.fn(), onFailed }, getStatus);

    for (let i = 0; i < SCAN_POLL_MAX_CONSECUTIVE_ERRORS; i += 1) {
      await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS);
    }

    expect(onFailed).toHaveBeenCalledWith("API offline");
  });
});
