import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
    name: "Scan eval",
    status: "completed",
    sleeve: "penny",
    universe: [],
    parameters: {},
    strategy_version: "v1",
    factor_model_version: "v1",
    primary_metrics: [],
    warnings: [],
    blockers: [],
    evidence_impact: "informational",
    verdict: "inconclusive",
    reliability_score: 50,
    research_notes: "",
  },
  interpretation: {
    verdict: "inconclusive",
    evidence_impact: "informational",
    conclusion: "Test",
    prose: "",
    supporting_observations: [],
    main_limitation: "Sample",
    suggested_next_action: "Review",
    reliability: { score: 50, factors: [] },
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
  charts: [
    {
      chart_id: "scan_recall_recall_at_10",
      title: "Stage A Recall@10 by algorithm",
      chart_type: "bar",
      series: [{ name: "Recall@10", data: [{ x: "stage_a_v2", y: 0.4 }] }],
    },
  ],
  metric_explanations: [],
  evidence_memory: [],
  related_runs: [],
  related_ideas: [],
  skipped_data: [],
};

describe("ScanEvaluationResultPanel", () => {
  it("shows production-not-modified notice", () => {
    render(<ScanEvaluationResultPanel detail={baseDetail} />);
    expect(
      screen.getAllByText(/Evaluation experiments do not automatically modify the production scan configuration/i).length
    ).toBeGreaterThan(0);
  });

  it("renders comparison metrics table", () => {
    render(<ScanEvaluationResultPanel detail={baseDetail} />);
    expect(screen.getAllByText("stage_a_v2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("0.4").length).toBeGreaterThan(0);
  });

  it("renders charts without crashing when present", () => {
    render(<ScanEvaluationResultPanel detail={baseDetail} />);
    expect(screen.getAllByText("Stage A Recall@10 by algorithm").length).toBeGreaterThan(0);
  });

  it("handles missing charts gracefully", () => {
    render(
      <ScanEvaluationResultPanel
        detail={{ ...baseDetail, charts: [] }}
        compact
      />
    );
    expect(screen.getAllByText("alphabetical_baseline").length).toBeGreaterThan(0);
  });

  it("shows warnings and limitations", () => {
    render(<ScanEvaluationResultPanel detail={baseDetail} />);
    expect(screen.getAllByText(/Survivorship bias possible/i).length).toBeGreaterThan(0);
  });
});
