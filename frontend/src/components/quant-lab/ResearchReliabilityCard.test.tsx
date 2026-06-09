import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResearchReliabilityCard } from "./ResearchReliabilityCard";
import { en } from "@/lib/i18n/messages/en";
import type { ResearchReliabilityScore } from "@/lib/researchReliability";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
}));

const baseScore = (overrides: Partial<ResearchReliabilityScore>): ResearchReliabilityScore => ({
  status: "usable_with_warnings",
  score_0_to_100: 65,
  reasons: ["adequateFactorCoverage"],
  warnings: ["icStale"],
  blockers: [],
  suggested_next_action: "runIcPanel",
  ...overrides,
});

describe("ResearchReliabilityCard", () => {
  it("renders badge, score, and sections", () => {
    render(<ResearchReliabilityCard score={baseScore({})} />);
    expect(screen.getByTestId("research-reliability-card")).toBeInTheDocument();
    expect(screen.getByTestId("research-reliability-badge")).toHaveTextContent(
      en.reliability.statusUsableWithWarnings
    );
    expect(screen.getByTestId("research-reliability-score")).toHaveTextContent("65");
    expect(screen.getByText(en.reliability.warnings.icStale)).toBeInTheDocument();
    expect(screen.getByText(en.reliability.actions.runIcPanel)).toBeInTheDocument();
  });

  it("shows blockers when present", () => {
    render(
      <ResearchReliabilityCard
        score={baseScore({
          status: "insufficient_data",
          blockers: ["noIcData"],
          score_0_to_100: 15,
        })}
      />
    );
    expect(screen.getByText(en.reliability.blockers.noIcData)).toBeInTheDocument();
  });
});
