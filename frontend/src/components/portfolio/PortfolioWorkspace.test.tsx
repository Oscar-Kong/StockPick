import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { PortfolioWorkspace } from "./PortfolioWorkspace";
import * as api from "@/lib/api";

const mockReplace = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => mockSearchParams,
}));

vi.mock("@/lib/i18n", async () => {
  const en = await import("@/lib/i18n/messages/en");
  return {
    useTranslation: () => ({ t: en.en, locale: "en" as const }),
    useTRef: () => ({ current: en.en }),
    fmt: (s: string, vars?: Record<string, string | number>) => {
      let out = s;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) out = out.replace(`{${k}}`, String(v));
      }
      return out;
    },
  };
});

vi.mock("./PortfolioResearch", () => ({
  PortfolioResearch: ({ active, holdingSymbols }: { active: boolean; holdingSymbols: string[] }) => (
    <div data-testid="research-tab" data-active={active} data-symbols={holdingSymbols.join(",")} />
  ),
}));

const dashboardFixture = {
  portfolio_value: 10000,
  cash: 1000,
  reserved_cash: 0,
  invested_value: 9000,
  cash_pct: 10,
  data_source: "csv",
  data_source_label: "Robinhood CSV",
  is_demo_data: false,
  portfolio_warnings: [],
  disclaimer: "Research only",
  holdings: [
    { symbol: "AAPL", shares: 10, avg_cost: 140, bucket: "penny" },
    { symbol: "MSFT", shares: 5, avg_cost: 280, bucket: "compounder" },
  ],
  decision: {
    items: [
      {
        symbol: "AAPL",
        decision: "buy",
        buy_pct: 60,
        keep_pct: 30,
        sell_pct: 10,
        suggested_action: "Add $100",
        suggested_dollar_action: 100,
        reasons: ["Momentum improving"],
        bucket: "penny",
        score: 80,
        risk_index: 0.3,
        price: 150,
        shares: 10,
        avg_cost: 140,
        market_value: 1500,
        risk_flags: [],
        current_weight: 0.15,
        target_weight: 0.2,
      },
    ],
  },
  top_penny_opportunities: [],
  closed_positions: [],
  risk_alerts: [],
  freshness: { overall_status: "fresh" },
};

describe("PortfolioWorkspace", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    for (const key of [...mockSearchParams.keys()]) mockSearchParams.delete(key);
    vi.spyOn(api, "getDailyDashboard").mockResolvedValue(dashboardFixture as never);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("defaults to Today tab content", async () => {
    render(<PortfolioWorkspace />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "Portfolio" })).toBeTruthy());
    expect(screen.getByRole("button", { name: "Run daily decision now" })).toBeTruthy();
  });

  it("shows buy keep sell percentages in holdings", async () => {
    render(<PortfolioWorkspace />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Run daily decision now" })).toBeTruthy());
    expect(document.body.textContent).toMatch(/60%/);
    expect(document.body.textContent).toMatch(/30%/);
    expect(document.body.textContent).toMatch(/10%/);
  });
});
