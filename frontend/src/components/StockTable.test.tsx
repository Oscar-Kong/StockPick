import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { StockTable } from "./StockTable";
import type { StockResult } from "@/lib/types";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
  useTRef: () => ({ current: en }),
  fmt: (template: string, vars: Record<string, string | number>) =>
    template.replace(/\{(\w+)\}/g, (_, key) => String(vars[key] ?? "")),
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
        onSelect={() => {}}
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
        onSelect={() => {}}
        onAddWatchlist={() => {}}
        heldPositions={new Map()}
      />
    );
    expect(screen.queryByText(/Held ·/)).not.toBeInTheDocument();
  });
});
