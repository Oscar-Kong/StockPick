import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PortfolioWorkspace } from "./PortfolioWorkspace";
import * as portfolioApi from "@/lib/api/portfolio";

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

const dailyTradingPlanFixture = {
  plan_id: "dtp_test_fixture",
  as_of: "2026-07-01T11:00:00-04:00",
  market_session: "regular",
  decision: "watch",
  confidence: 75,
  summary: "Watch qualified setup until entry window opens.",
  current_short_term_exposure_pct: 15,
  maximum_short_term_exposure_pct: 50,
  available_risk_capacity_pct: 35,
  active_short_term_positions: 1,
  focus_list: [
    {
      symbol: "AAPL",
      rank: 1,
      status: "qualified",
      reasons: ["Manage existing position"],
      rejection_reasons: [],
    },
  ],
  primary_candidate: {
    symbol: "AAPL",
    action: "manage",
    entry_not_before: "10:00 America/New_York",
    entry_condition: "Manage existing short-term position",
    reference_entry_price: 150,
    maximum_position_value: 1500,
    maximum_portfolio_weight_pct: 15,
    stop_price: 142.5,
    stop_loss_pct: 5,
    first_target_price: 165,
    first_target_gain_pct: 10,
    first_target_sell_fraction_pct: 50,
    remaining_position_plan: "Trail stop",
    trend_state: "existing_position",
    sector_leadership: {},
    volume_classification: "n/a",
    news_classification: "n/a",
    risk_reward_ratio: 2,
    data_confidence: 80,
    supporting_evidence: ["Active short-term holding"],
    risk_flags: [],
  },
  cash_reason: null,
  rule_checklist: [
    { rule_id: "MAX_EXPOSURE", label: "Exposure cap", status: "pass", evidence: "15% vs 50%" },
  ],
  rejected_candidates: [],
  holiday_risk: { is_pre_holiday_session: false, recommend_reduce_exposure: false, reason: null },
  review_prompts: [],
  data_freshness: { as_of: "2026-07-01T11:00:00-04:00" },
  disclaimer: "Research and decision support only. No order has been placed.",
};

const dashboardFixture = {
  portfolio_value: 10000,
  cash: 1000,
  reserved_cash: 0,
  invested_value: 9000,
  cash_pct: 10,
  data_source: "csv",
  data_source_label: "Robinhood CSV",
  robinhood_mcp_enabled: true,
  robinhood_mcp_authenticated: false,
  is_demo_data: false,
  portfolio_warnings: [],
  disclaimer: "Research only",
  holdings: [
    { symbol: "AAPL", shares: 10, avg_cost: 140, bucket: "penny" },
    { symbol: "MSFT", shares: 5, avg_cost: 280, bucket: "compounder" },
  ],
  decision: {
    as_of: "2026-07-01",
    cash: 1000,
    total_value: 10000,
    invested_value: 9000,
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
  freshness: { overall_status: "fresh", items: [], refresh_recommended: false, refresh_in_progress: false },
  daily_trading_plan: dailyTradingPlanFixture,
};

describe("PortfolioWorkspace", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    for (const key of [...mockSearchParams.keys()]) mockSearchParams.delete(key);
    vi.spyOn(portfolioApi, "getDailyDashboard").mockResolvedValue(dashboardFixture as never);
    vi.spyOn(portfolioApi, "getDailyTradingPlanReview").mockResolvedValue(null);
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

  it("shows buy keep sell percentages in holdings on Today tab", async () => {
    render(<PortfolioWorkspace />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Run daily decision now" })).toBeTruthy());
    expect(document.body.textContent).toMatch(/60%/);
    expect(document.body.textContent).toMatch(/30%/);
    expect(document.body.textContent).toMatch(/10%/);
  });

  it("does not show Daily Trading Plan on Today tab", async () => {
    render(<PortfolioWorkspace />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Run daily decision now" })).toBeTruthy());
    expect(screen.queryByText("Policy-gated short-term plan — decision support only")).not.toBeInTheDocument();
  });

  it("loads the dashboard once on mount (no request storm)", async () => {
    render(<PortfolioWorkspace />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Run daily decision now" })).toBeTruthy());
    await new Promise((r) => setTimeout(r, 100));
    expect(portfolioApi.getDailyDashboard).toHaveBeenCalledTimes(1);
  });

  it("renders Daily Trading Plan on Daily Plan tab", async () => {
    render(<PortfolioWorkspace />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Daily Plan" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Daily Plan" }));
    expect(screen.getByText("Daily Trading Plan")).toBeInTheDocument();
    expect(screen.getByText("Watch")).toBeInTheDocument();
    expect(screen.getByText(/15\.0% used · 35\.0% room · 50% cap/)).toBeInTheDocument();
    expect(screen.getByText(/Exposure cap/)).toBeInTheDocument();
  });
});
