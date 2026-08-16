import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n";
import { ActivePositionMonitorPanel } from "./ActivePositionMonitorPanel";

const getActivePositionMonitor = vi.fn();
const runActivePositionMonitor = vi.fn();

vi.mock("@/lib/api/portfolio", () => ({
  getActivePositionMonitor: (...args: unknown[]) => getActivePositionMonitor(...args),
  runActivePositionMonitor: (...args: unknown[]) => runActivePositionMonitor(...args),
}));

afterEach(() => vi.clearAllMocks());

describe("ActivePositionMonitorPanel", () => {
  it("shows a readable state, freshness, and read-only boundary", async () => {
    getActivePositionMonitor.mockResolvedValue({
      as_of: "2026-08-16T14:30:30Z",
      quote_as_of: "2026-08-16T14:30:00Z",
      statuses: [
        {
          symbol: "TEST",
          bucket: "penny",
          state: "EXIT_WARNING",
          actionable: false,
          price: 9.55,
          data_status: "fresh",
          shares: 10,
          avg_cost: 10,
          unrealized_pl_pct: -4.5,
          distance_to_stop_pct: 0.5,
          distance_to_target_pct: -13.2,
          evidence: ["Price is 0.5% above stop/invalidation"],
        },
      ],
      transitions: [],
      notifications: [],
      quote_only: true,
      execution_enabled: false,
    });

    render(
      <LocaleProvider>
        <ActivePositionMonitorPanel />
      </LocaleProvider>,
    );

    expect(await screen.findByText("TEST")).toBeInTheDocument();
    expect(screen.getByText("Exit warning")).toBeInTheDocument();
    expect(screen.getByText("Fresh")).toBeInTheDocument();
    expect(screen.getByText("Decision support only · no trades are placed")).toBeInTheDocument();
  });
});
