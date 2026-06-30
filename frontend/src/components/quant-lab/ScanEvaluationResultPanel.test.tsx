import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { ScanEvaluationResultPanel } from "./ScanEvaluationResultPanel";
import type { ResearchRunDetailResponse } from "@/lib/types";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
}));

const baseDetail: ResearchRunDetailResponse = {
  summary: {
    run_id: "scan_evaluation:test",
    run_type: "scan_evaluation",
    name: "Scan eval penny",
    status: "completed",
    sleeve: "penny",
    universe: [],
    parameters: {
      bucket: "penny",
      start_date: "2024-01-01",
      end_date: "2024-06-01",
      algorithm_versions: ["alphabetical_baseline", "stage_a_v2"],
    },
    strategy_version: "v1",
    factor_model_version: "v1",
    primary_metrics: [],
    warnings: [],
    blockers: [],
    evidence_impact: "informational",
    verdict: "inconclusive",
    reliability_score: 50,
    research_notes: "",
    archived: false,
    result_reference: { store: "quant_lab", run_id: "scan_evaluation:test", detail_path: null },
  },
  interpretation: {
    verdict: "inconclusive",
    evidence_impact: "informational",
    conclusion: "stage_a_v2 leads on recall",
    prose: "",
    supporting_observations: [],
    main_limitation: "Sample",
    suggested_next_action: "Review",
    reliability: { score: 50, status: "moderate", reasons: [] },
    major_evidence_gate: {},
  },
  experiment: null,
  detail: {
    quant_lab: {
      mode: "comparison",
      comparison_table: [
        {
          algorithm_version: "alphabetical_baseline",
          recall_at_10: 0.1,
          recall_at_20: 0.2,
          recall_at_50: 0.3,
          rebalance_count: 2,
        },
        {
          algorithm_version: "stage_a_v2",
          recall_at_10: 0.4,
          recall_at_20: 0.5,
          recall_at_50: 0.6,
          rebalance_count: 2,
        },
      ],
    },
    caveats: [
      "Evaluation experiments do not automatically modify the production scan configuration.",
      "Survivorship bias possible when universe_pit is empty.",
    ],
  },
  charts: [],
  metric_explanations: [],
  evidence_memory: [],
  related_runs: [],
  related_ideas: [],
  skipped_data: [],
};

describe("ScanEvaluationResultPanel", () => {
  afterEach(() => cleanup());

  it("shows production-not-modified notice", () => {
    render(<ScanEvaluationResultPanel detail={baseDetail} />);
    expect(screen.getByText(/Evaluation experiments do not automatically modify/i)).toBeInTheDocument();
  });

  it("renders algorithm comparison cards with formatted recall", () => {
    render(<ScanEvaluationResultPanel detail={baseDetail} />);
    expect(screen.getAllByRole("heading", { name: "Stage A v2" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("40.0%").length).toBeGreaterThan(0);
    expect(screen.getByText("Best Recall@10")).toBeInTheDocument();
  });

  it("shows run context in full variant", () => {
    render(<ScanEvaluationResultPanel detail={baseDetail} variant="full" />);
    expect(screen.getAllByText(/2024-01-01 → 2024-06-01/).length).toBeGreaterThan(0);
  });

  it("compact variant omits full metrics table by default", () => {
    const { container } = render(<ScanEvaluationResultPanel detail={baseDetail} variant="compact" />);
    expect(container.querySelector("details")).toBeNull();
    expect(screen.getAllByRole("heading", { name: "Stage A v2" }).length).toBeGreaterThan(0);
  });

  it("shows limitations in collapsible section", () => {
    render(<ScanEvaluationResultPanel detail={baseDetail} variant="full" />);
    expect(screen.getAllByText("Limitations & caveats").length).toBeGreaterThan(0);
  });
});
