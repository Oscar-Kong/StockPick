import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { ModelMonitorTab } from "./ModelMonitorTab";

const tRef = { current: en };

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
  useTRef: () => tRef,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  getModelMonitor: vi.fn().mockResolvedValue({
    sleeve: "penny",
    factor_health: [],
    prediction_health: { resolved_count: 0, unresolved_count: 0, stale_count: 0, calibration_ready: false },
    data_health: { integrity_blockers: [] },
    research_jobs: [],
    model_configuration: { strategy_version: "v1", factor_model_version: "f1", read_only: true },
  }),
  getV2Audit: vi.fn().mockResolvedValue({ events: [] }),
  listEvidenceReview: vi.fn().mockResolvedValue({ findings: [], total: 0 }),
  retryResearchJob: vi.fn(),
  postEvidenceReviewAction: vi.fn(),
}));

vi.mock("./DataQualityTab", () => ({
  DataQualityTab: () => <div data-testid="data-quality-embed">DQ</div>,
}));

describe("ModelMonitorTab", () => {
  it("renders monitor hint", async () => {
    render(<ModelMonitorTab sleeve="penny" onSleeveChange={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(en.quantLab.monitorHint)).toBeInTheDocument();
    });
  });
});
