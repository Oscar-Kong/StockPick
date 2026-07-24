import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { ScanScoreBandLegend, ScanScoreBreakdown } from "./ScanScoreBreakdown";
import type { StockResult } from "@/lib/types";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
}));

afterEach(() => cleanup());

function stock(overrides: Partial<StockResult> = {}): StockResult {
  return {
    symbol: "ABC",
    score: 70,
    price: 5,
    risk_level: "high",
    signals: [],
    metrics: {},
    ...overrides,
  } as StockResult;
}

describe("ScanScoreBreakdown", () => {
  it("shows score with Strong band at ≥70", () => {
    render(
      <ScanScoreBreakdown
        stock={stock({ ranking_score: 72 })}
        compact
        scanScores={[50, 60, 72]}
      />
    );
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("Strong")).toBeInTheDocument();
  });

  it("labels fallback 100s so they are not mistaken for Strong", () => {
    const { container } = render(
      <ScanScoreBreakdown
        stock={stock({
          score: 100,
          ranking_score: 100,
          metrics: { provider_limited_partial_data: true, ranking_score: 100 },
        })}
        compact
      />
    );
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(container.querySelector(".scan-score-band--fallback")).toHaveTextContent("Fallback");
    expect(container.querySelector(".scan-score-band--strong")).toBeNull();
  });

  it("renders the band legend", () => {
    render(<ScanScoreBandLegend />);
    expect(screen.getByText(/Score guide: Strong ≥70/i)).toBeInTheDocument();
  });
});
