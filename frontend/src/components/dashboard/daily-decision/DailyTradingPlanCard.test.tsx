import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { DailyTradingPlanCard } from "./DailyTradingPlanCard";
import type { DailyDashboardResponse, DailyTradingPlanResponse } from "@/lib/types";

vi.mock("@/lib/i18n", async () => {
  const en = await import("@/lib/i18n/messages/en");
  return {
    useTranslation: () => ({ t: en.en, locale: "en" as const }),
  };
});

vi.mock("@/lib/api/portfolio", () => ({
  getDailyTradingPlanReview: vi.fn().mockResolvedValue(null),
  saveDailyTradingPlanReview: vi.fn(),
}));

const basePlan: DailyTradingPlanResponse = {
  plan_id: "dtp_test",
  as_of: "2026-07-01T11:00:00-04:00",
  market_session: "regular",
  decision: "buy",
  confidence: 82,
  summary: "Primary buy candidate STRONG from latest cached penny scan.",
  current_short_term_exposure_pct: 12,
  maximum_short_term_exposure_pct: 50,
  available_risk_capacity_pct: 38,
  active_short_term_positions: 0,
  focus_list: [
    { symbol: "STRONG", rank: 1, status: "qualified", reasons: ["Trend confirmed"], rejection_reasons: [] },
  ],
  primary_candidate: {
    symbol: "STRONG",
    action: "buy",
    entry_not_before: "10:00 America/New_York",
    entry_condition: "Confirmed trend",
    reference_entry_price: 10,
    maximum_position_value: 5000,
    maximum_portfolio_weight_pct: 50,
    stop_price: 9.5,
    stop_loss_pct: 5,
    first_target_price: 11,
    first_target_gain_pct: 10,
    first_target_sell_fraction_pct: 50,
    remaining_position_plan: "Trail remainder",
    trend_state: "confirmed",
    sector_leadership: {},
    volume_classification: "breakout_confirmation",
    news_classification: "no_actionable_news_edge",
    risk_reward_ratio: 2,
    data_confidence: 85,
    supporting_evidence: ["Elevated volume at resistance break"],
    risk_flags: [],
  },
  cash_reason: null,
  rule_checklist: [
    { rule_id: "MAX_EXPOSURE", label: "Exposure cap", status: "pass", evidence: "12% vs 50%" },
    { rule_id: "ENTRY_TIME", label: "Entry after 10:00 ET", status: "pass", evidence: "open" },
  ],
  rejected_candidates: [],
  holiday_risk: { is_pre_holiday_session: false, recommend_reduce_exposure: false, reason: null },
  review_prompts: [],
  data_freshness: { as_of: "2026-07-01T11:00:00-04:00" },
  disclaimer: "Research and decision support only. No order has been placed.",
};

function dashboard(overrides: Partial<DailyDashboardResponse> = {}): DailyDashboardResponse {
  return {
    portfolio_value: 10000,
    cash: 5000,
    data_source: "csv",
    data_source_label: "CSV",
    holdings: [{ symbol: "AAPL", shares: 10, avg_cost: 100, bucket: "compounder" }],
    top_penny_opportunities: [],
    portfolio_warnings: [],
    disclaimer: "",
    daily_trading_plan: basePlan,
    ...overrides,
  };
}

describe("DailyTradingPlanCard", () => {
  afterEach(() => {
    cleanup();
  });

  function openTradeSetup() {
    const summaries = screen.getAllByText((_, el) => el?.tagName === "SUMMARY" && /Trade setup/.test(el.textContent ?? ""));
    fireEvent.click(summaries[0]!);
  }

  it("renders buy decision and exposure ceiling", () => {
    render(<DailyTradingPlanCard data={dashboard()} />);
    expect(screen.getByText("Buy")).toBeInTheDocument();
    expect(screen.getByText(/12\.0% used · 38\.0% room · 50% cap/)).toBeInTheDocument();
  });

  it("renders stay in cash plan", () => {
    const cashPlan = { ...basePlan, decision: "stay_in_cash" as const, primary_candidate: null, cash_reason: "No qualified setup" };
    render(<DailyTradingPlanCard data={dashboard({ daily_trading_plan: cashPlan })} />);
    expect(screen.getByText("Stay in Cash")).toBeInTheDocument();
    expect(screen.getByText("No qualified setup")).toBeInTheDocument();
  });

  it("renders watch pre-entry gate in candidate action", () => {
    const watchPlan = {
      ...basePlan,
      decision: "watch" as const,
      primary_candidate: { ...basePlan.primary_candidate!, action: "watch" },
    };
    render(<DailyTradingPlanCard data={dashboard({ daily_trading_plan: watchPlan })} />);
    expect(screen.getByText("Watch")).toBeInTheDocument();
    openTradeSetup();
    expect(screen.getAllByText(/10:00 America\/New_York/).length).toBeGreaterThan(0);
  });

  it("shows stop and target presentation inside trade setup", () => {
    render(<DailyTradingPlanCard data={dashboard()} />);
    openTradeSetup();
    expect(screen.getByText("First target")).toBeInTheDocument();
    expect(screen.getByText(/Sell 50% at target/)).toBeInTheDocument();
    expect(screen.getByText("Risk / reward")).toBeInTheDocument();
  });

  it("shows failed rule visibility", () => {
    const failPlan = {
      ...basePlan,
      decision: "watch" as const,
      rule_checklist: [
        { rule_id: "ENTRY_TIME", label: "Entry after 10:00 ET", status: "fail", evidence: "Before window" },
      ],
    };
    render(<DailyTradingPlanCard data={dashboard({ daily_trading_plan: failPlan })} />);
    const rule = screen.getByText(/Before window/);
    expect(within(rule.closest("li")!).getByText("Fail")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    render(<DailyTradingPlanCard data={dashboard()} loading />);
    expect(screen.getByText(/Loading trading plan/)).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<DailyTradingPlanCard data={dashboard({ daily_trading_plan: null })} />);
    expect(screen.getByText(/Trading plan unavailable/)).toBeInTheDocument();
  });

  it("renders API error state", () => {
    render(<DailyTradingPlanCard data={dashboard()} error="Network error" />);
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });
});
