import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { formatDateTime } from "@/lib/datetime";
import { StockTable } from "./StockTable";
import type { StockResult } from "@/lib/types";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
  useTRef: () => ({ current: en }),
  fmt: (template: string, vars: Record<string, string | number>) =>
    template.replace(/\{(\w+)\}/g, (_, key) => String(vars[key] ?? "")),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const sample: StockResult = {
  symbol: "LIDR",
  price: 1.61,
  score: 72,
  signals: [],
  risk_level: "high",
  summary: "Test",
  bucket: "penny",
  metrics: { change_pct_1d: 2.5 },
};

describe("StockTable holdings badge", () => {
  afterEach(() => cleanup());

  it("shows held badge when symbol is in portfolio map", () => {
    const held = new Map([["LIDR", { shares: 10, avgCost: 1.91 }]]);
    render(
      <StockTable
        results={[sample]}
        onAddWatchlist={() => {}}
        heldPositions={held}
      />
    );
    expect(screen.getByText("Held · 10 sh")).toBeInTheDocument();
    expect(screen.getByText(/1 already held/)).toBeInTheDocument();
  });

  it("omits held badge for symbols not owned", () => {
    render(
      <StockTable
        results={[sample]}
        onAddWatchlist={() => {}}
        heldPositions={new Map()}
      />
    );
    expect(screen.queryByText(/Held ·/)).not.toBeInTheDocument();
  });

  it("shows scan timestamp next to results count when scanAt is set", () => {
    const scanAt = "2026-06-23T15:30:00Z";
    render(
      <StockTable
        results={[sample]}
        onAddWatchlist={() => {}}
        scanAt={scanAt}
      />
    );
    expect(screen.getByText(new RegExp(formatDateTime(scanAt)))).toBeInTheDocument();
  });

  it("labels penny stability and entry risk as a daily proxy", () => {
    render(
      <StockTable
        results={[
          {
            ...sample,
            metrics: {
              recommendation: "watch",
              buy_pct: 20,
              wait_pct: 80,
              trade_hint_reason: "Good candidate, poor entry",
              stability_score: 82,
              stability_classification: "stable",
              entry_risk_score: 75,
              entry_risk_classification: "extended",
              entry_risk_source: "daily_ohlcv_proxy",
            },
          },
        ]}
        onAddWatchlist={() => {}}
      />
    );

    expect(screen.getByText("Stability 82 · stable")).toBeInTheDocument();
    expect(screen.getByText("Entry risk 75 · extended · daily proxy")).toBeInTheDocument();
  });
});
