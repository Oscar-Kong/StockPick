import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor, fireEvent } from "@testing-library/react";
import { TradingHistoryModule } from "./TradingHistoryModule";
import * as portfolioApi from "@/lib/api/portfolio";

vi.mock("@/lib/i18n", async () => {
  const en = await import("@/lib/i18n/messages/en");
  return {
    useTranslation: () => ({ t: en.en, locale: "en" }),
    fmt: (s: string, vars?: Record<string, string | number>) => {
      let out = s;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) out = out.replace(`{${k}}`, String(v));
      }
      return out;
    },
  };
});

const ledgerFixture = {
  rows: [
    {
      id: 1,
      symbol: "AMC",
      side: "buy",
      row_type: "buy",
      quantity: 10,
      price: 5,
      amount: -50,
      trans_code: "MCP-BUY",
      description: null,
      activity_date: "1/15/2026",
      process_date: null,
      executed_at: null,
      source: "manual",
      row_hash: "a",
      locked: true,
    },
    {
      id: 2,
      symbol: "AMC",
      side: "sell",
      row_type: "sell",
      quantity: 5,
      price: 6,
      amount: 30,
      trans_code: "MCP-SELL",
      description: null,
      activity_date: "3/20/2025",
      process_date: null,
      executed_at: null,
      source: "manual",
      row_hash: "b",
      locked: true,
    },
  ],
  open_holdings: [],
  closed_positions: [],
  ledger_cash_estimate: 0,
  warnings: [],
};

describe("TradingHistoryModule", () => {
  beforeEach(() => {
    vi.spyOn(portfolioApi, "getPortfolioLedger").mockResolvedValue(ledgerFixture as never);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders trades and filters by year", async () => {
    render(<TradingHistoryModule onSync={() => {}} />);
    await waitFor(() => expect(screen.getByText("AMC")).toBeTruthy());

    const yearSelect = screen.getByLabelText("Year") as HTMLSelectElement;
    fireEvent.change(yearSelect, { target: { value: "2025" } });

    await waitFor(() => {
      expect(screen.queryByText("1/15/2026")).not.toBeInTheDocument();
      expect(screen.getByText("3/20/2025")).toBeInTheDocument();
    });
  });
});
