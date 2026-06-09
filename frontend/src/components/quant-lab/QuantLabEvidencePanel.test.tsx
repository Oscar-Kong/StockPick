import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup, fireEvent } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { QuantLabEvidencePanel } from "./QuantLabEvidencePanel";
import * as api from "@/lib/api";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
}));

vi.mock("@/lib/api", () => ({
  getQuantLabEvidence: vi.fn(),
  runWalkForwardResearch: vi.fn(),
  runPairsResearch: vi.fn(),
}));

const mocked = vi.mocked(api);

const unavailable = (id: string, researchOnly = false) => ({
  id,
  available: false,
  reason: "No saved run found",
  stale: false,
  warnings: [],
  trust_indicator: "no_saved_run" as const,
  research_only: researchOnly,
  tab: id === "factor_ic" ? "factor-performance" : id.replace("_", "-"),
});

describe("QuantLabEvidencePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders last-run cards with available data", async () => {
    mocked.getQuantLabEvidence.mockResolvedValue({
      sleeve: "medium",
      generated_at: "2026-06-05",
      validation_copy: en.quantLab.validationCopy,
      factor_ic: {
        id: "factor_ic",
        available: true,
        generated_at: "2026-06-01",
        sample_size: 1200,
        main_metric: { label: "Mean IC", value: "0.038" },
        stale: false,
        warnings: [],
        trust_indicator: "fresh",
        research_only: false,
        tab: "factor-performance",
      },
      walk_forward: unavailable("walk_forward", true),
      predictions: unavailable("predictions"),
      pairs: unavailable("pairs", true),
      jobs: unavailable("jobs"),
    });
    render(<QuantLabEvidencePanel onNavigateTab={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText(en.quantLab.lastRunFactorIc)).toBeInTheDocument();
    });
    expect(screen.getByText(en.quantLab.trustFresh)).toBeInTheDocument();
    expect(screen.getByText("0.038")).toBeInTheDocument();
    expect(mocked.runWalkForwardResearch).not.toHaveBeenCalled();
    expect(mocked.runPairsResearch).not.toHaveBeenCalled();
  });

  it("shows no saved run and stale badges", async () => {
    mocked.getQuantLabEvidence.mockResolvedValue({
      sleeve: "medium",
      generated_at: "2026-06-05",
      validation_copy: en.quantLab.validationCopy,
      factor_ic: {
        id: "factor_ic",
        available: true,
        generated_at: "2026-01-01",
        stale: true,
        stale_reason: "Factor IC panel is 30 days old",
        warnings: ["Factor IC panel is 30 days old"],
        trust_indicator: "stale",
        research_only: false,
        tab: "factor-performance",
      },
      walk_forward: unavailable("walk_forward", true),
      predictions: unavailable("predictions"),
      pairs: unavailable("pairs", true),
      jobs: unavailable("jobs"),
    });
    render(<QuantLabEvidencePanel onNavigateTab={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText(en.quantLab.trustStale)).toBeInTheDocument();
    });
    expect(screen.getByText(/30 days old/)).toBeInTheDocument();
  });

  it("navigates on view details without running research", async () => {
    const onNavigate = vi.fn();
    mocked.getQuantLabEvidence.mockResolvedValue({
      sleeve: "medium",
      generated_at: "2026-06-05",
      validation_copy: en.quantLab.validationCopy,
      factor_ic: unavailable("factor_ic"),
      walk_forward: {
        ...unavailable("walk_forward", true),
        tab: "walk-forward",
      },
      predictions: unavailable("predictions"),
      pairs: { ...unavailable("pairs", true), tab: "pairs" },
      jobs: unavailable("jobs"),
    });
    render(<QuantLabEvidencePanel onNavigateTab={onNavigate} />);
    await waitFor(() => {
      expect(screen.getAllByText(en.quantLab.runNewResearch).length).toBeGreaterThan(0);
    });
    fireEvent.click(screen.getAllByText(en.quantLab.runNewResearch)[0]);
    expect(onNavigate).toHaveBeenCalledWith("walk-forward");
    expect(mocked.runWalkForwardResearch).not.toHaveBeenCalled();
  });
});
