import { afterEach, describe, expect, it, vi } from "vitest";
import {
  RobinhoodMcpSyncTimeoutError,
  syncRobinhoodMcp,
} from "@/lib/api/portfolio";

const startMock = vi.fn();
const jobMock = vi.fn();

vi.mock("@/lib/api/client", () => ({
  request: (path: string, opts?: { method?: string }) => {
    if (path.startsWith("/brokerage/sync/robinhood-mcp/") && !opts?.method) {
      return jobMock();
    }
    if (path.startsWith("/brokerage/sync/robinhood-mcp") && opts?.method === "POST") {
      return startMock();
    }
    throw new Error(`unexpected request ${opts?.method ?? "GET"} ${path}`);
  },
  resolveApiBaseUrl: () => "http://localhost",
}));

describe("syncRobinhoodMcp", () => {
  afterEach(() => {
    startMock.mockReset();
    jobMock.mockReset();
  });

  it("treats completed cash-only sync as success", async () => {
    startMock.mockResolvedValue({ job_id: "j1", status: "running" });
    jobMock.mockResolvedValue({
      job_id: "j1",
      status: "completed",
      result: { holdings_count: 0, cash: 2105.82 },
    });

    const result = await syncRobinhoodMcp(true);
    expect(result.holdings_count).toBe(0);
    expect(result.cash).toBe(2105.82);
  });

  it("treats completed status without result body as success", async () => {
    startMock.mockResolvedValue({ job_id: "j2", status: "running" });
    jobMock.mockResolvedValue({
      job_id: "j2",
      status: "completed",
      result: null,
      message: "ok",
    });

    const result = await syncRobinhoodMcp(false);
    expect(result.message).toBe("ok");
  });

  it("exposes soft timeout as RobinhoodMcpSyncTimeoutError", () => {
    const err = new RobinhoodMcpSyncTimeoutError("still running");
    expect(err.soft).toBe(true);
    expect(err).toBeInstanceOf(Error);
  });
});
