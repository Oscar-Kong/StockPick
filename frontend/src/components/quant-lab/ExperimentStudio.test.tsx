import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { ExperimentStudio } from "./ExperimentStudio";
import * as api from "@/lib/api";

const tRef = { current: en };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams("section=experiments&step=choose"),
}));

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
  useTRef: () => tRef,
}));

vi.mock("@/lib/api", () => ({
  getExperimentTemplates: vi.fn(),
  getExperimentPresets: vi.fn(),
  validateResearchExperiment: vi.fn(),
  createResearchExperiment: vi.fn(),
  updateResearchExperiment: vi.fn(),
  launchResearchExperiment: vi.fn(),
  getExperimentJob: vi.fn(),
}));

const mocked = vi.mocked(api);

describe("ExperimentStudio", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocked.getExperimentTemplates.mockResolvedValue({
      templates: [
        {
          experiment_type: "walk_forward",
          title: "Walk-Forward Ranking Test",
          description: "WF test",
          required_fields: ["sleeve"],
          optional_fields: [],
          universe_sources: ["full_bucket"],
          supports_presets: true,
        },
        {
          experiment_type: "pairs_discovery",
          title: "Pairs Discovery",
          description: "Pairs",
          required_fields: ["symbols"],
          optional_fields: [],
          universe_sources: ["custom_symbols"],
          supports_presets: true,
        },
        {
          experiment_type: "scan_evaluation",
          title: "Scan Selection Evaluation",
          description: "Compare scan algorithms",
          required_fields: ["bucket"],
          optional_fields: [],
          universe_sources: ["full_bucket"],
          supports_presets: true,
        },
      ],
    });
    mocked.getExperimentPresets.mockResolvedValue({
      presets: [
        {
          preset_id: "quick_check",
          title: "Quick Check",
          description: "Fast",
          major_evidence_eligible: false,
          verdict_ceiling: "exploratory",
          parameters: [{ key: "max_symbols", value: 15, description: "" }],
        },
      ],
    });
  });

  it("lists templates when API returns templates", async () => {
    render(<ExperimentStudio sleeve="penny" onSleeveChange={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Walk-Forward Ranking Test")).toBeInTheDocument());
    expect(screen.getByText("Pairs Discovery")).toBeInTheDocument();
    expect(screen.getByText("Scan Selection Evaluation")).toBeInTheDocument();
  });

  it("shows research-only choose hint", async () => {
    render(<ExperimentStudio sleeve="penny" onSleeveChange={() => undefined} />);
    await waitFor(() => expect(screen.getByText(/Pick a research template/i)).toBeInTheDocument());
  });
});
