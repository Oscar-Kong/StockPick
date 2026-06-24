import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { ScanScoreBreakdown } from "./ScanScoreBreakdown";
import type { StockResult } from "@/lib/types";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
}));

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
  it("shows a single score when confidence and tradability are neutral", () => {
    render(
      <ScanScoreBreakdown
        stock={stock({
          ranking_score: 68,
          alpha_score: 82,
          confidence_score: 50,
          tradability_score: 50,
        })}
        compact
      />
    );
    expect(screen.getByText("68")).toBeInTheDocument();
    expect(screen.queryByText("Conf")).not.toBeInTheDocument();
    expect(screen.queryByText("Trade")).not.toBeInTheDocument();
    expect(screen.queryByText("Alpha")).not.toBeInTheDocument();
  });

  it("shows non-neutral pillars in compact mode", () => {
    render(
      <ScanScoreBreakdown
        stock={stock({
          ranking_score: 72,
          confidence_score: 38,
          tradability_score: 50,
        })}
        compact
      />
    );
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("Conf")).toBeInTheDocument();
    expect(screen.queryByText("Trade")).not.toBeInTheDocument();
  });

  it("falls back to legacy score without decomposed fields", () => {
    render(<ScanScoreBreakdown stock={stock({ score: 77 })} compact />);
    expect(screen.getByText("77")).toBeInTheDocument();
  });
});
