import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PortfolioPage } from "@/components/PortfolioPage";
import * as api from "@/lib/api";

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

vi.mock("@/components/portfolio/PortfolioRiskTab", () => ({
  PortfolioRiskTab: () => <div>Risk tab</div>,
}));

vi.mock("@/components/ChartMount", () => ({
  ChartMount: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));

const summaryFixture = {
  as_of: "2026-06-16T20:00:00Z",
  total_value: 10000,
  invested_value: 9000,
  cash: 1000,
  cash_weight: 0.1,
  active_holdings_count: 2,
  positions: [
    {
      symbol: "AAPL",
      shares: 10,
      price: 150,
      market_value: 1500,
      avg_cost: 140,
      weight: 0.15,
    },
    {
      symbol: "MSFT",
      shares: 5,
      price: 300,
      market_value: 1500,
      avg_cost: 280,
      weight: 0.15,
    },
  ],
  source: "portfolio_ledger",
  data_source: "csv",
  data_source_label: "Robinhood CSV",
  stale: false,
  warnings: [],
  disclaimer: "Research only",
};

describe("PortfolioPage", () => {
  beforeEach(() => {
    vi.spyOn(api, "getPortfolioSummary").mockResolvedValue(summaryFixture);
    vi.spyOn(api, "getWatchlist").mockResolvedValue([
      { symbol: "AAPL", added_at: "", notes: "", bucket: "penny" },
      { symbol: "MSFT", added_at: "", notes: "", bucket: "compounder" },
    ]);
    vi.spyOn(api, "getPortfolioFactorExposure").mockResolvedValue({
      diagnostic_only: true,
      benchmark: "SPY",
      lookback_period: "1y",
      symbols_requested: ["AAPL", "MSFT"],
      symbols_used: ["AAPL", "MSFT"],
      excluded: [],
      observation_count: 100,
      betas: {},
      correlation: {},
      pca: { sufficient: true, symbol_loadings: [], explained_variance_ratio: [0.5] },
      concentration_warning: false,
      notes: [],
    });
  });

  it("renders Overview tab by default with summary metrics", async () => {
    render(<PortfolioPage />);
    await waitFor(() => {
      expect(screen.getByText("$10,000")).toBeTruthy();
    });
    expect(screen.getByText("Overview")).toBeTruthy();
  });

  it("links to Home daily decisions", async () => {
    render(<PortfolioPage />);
    const links = await screen.findAllByRole("link", { name: /View Daily Decisions/i });
    expect(links[0]?.getAttribute("href")).toBe("/#daily-decisions");
  });

  it("passes selected sleeve to policy backtest API", async () => {
    const backtestSpy = vi.spyOn(api, "runPortfolioPolicyBacktest").mockResolvedValue({
      policy: "equal_weight",
      rebalance: "monthly",
      engine: "policy_sim",
      lookback_period: "1y",
      symbols_requested: ["AAPL", "MSFT"],
      symbols_used: ["AAPL", "MSFT"],
      excluded: [],
      initial_capital: 100000,
      final_capital: 105000,
      total_return_pct: 5,
      annualized_return_pct: 4,
      max_drawdown_pct: -3,
      volatility_pct: 10,
      sharpe_ratio: 0.9,
      benchmark_return_pct: 6,
      turnover_pct: 15,
      rebalance_count: 2,
      equity_curve: [],
      weights_history: [],
      notes: [],
    });

    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getAllByText("$10,000").length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByRole("button", { name: "Backtest" })[0]!);
    const selects = document.querySelectorAll("select");
    const sleeveSelect = Array.from(selects).find((s) =>
      Array.from(s.options).some((o) => o.value === "compounder")
    ) as HTMLSelectElement | undefined;
    if (sleeveSelect) {
      fireEvent.change(sleeveSelect, { target: { value: "compounder" } });
    }
    const runBtn = screen.getByRole("button", { name: /Run policy backtest/i });
    fireEvent.click(runBtn);

    await waitFor(() => expect(backtestSpy).toHaveBeenCalled());
    expect(backtestSpy.mock.calls[0]?.[0]?.sleeve).toBe("compounder");
  });

  it("shows Rebalance tab with feasibility section", async () => {
    render(<PortfolioPage />);
    const tabs = screen.getAllByRole("button", { name: "Rebalance" });
    fireEvent.click(tabs[0]!);
    await waitFor(() => {
      expect(document.body.textContent).toMatch(/Constraint set is feasible|capacity/i);
    });
  });
});
