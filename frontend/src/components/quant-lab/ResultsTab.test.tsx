import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { ResultsTab } from "./ResultsTab";

const tRef = { current: en };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
  useTRef: () => tRef,
}));

vi.mock("@/lib/api", () => ({
  listResearchRuns: vi.fn().mockResolvedValue({ runs: [], total: 0, offset: 0, limit: 20 }),
  getResearchRunDetail: vi.fn(),
  compareResearchRunsDetail: vi.fn(),
  patchResearchRunArchive: vi.fn(),
  patchResearchRunNotes: vi.fn(),
  duplicateResearchRunExperiment: vi.fn(),
  createResearchRunFollowUpIdea: vi.fn(),
  exportResearchRun: vi.fn(),
}));

describe("ResultsTab", () => {
  it("renders results index hint", async () => {
    render(<ResultsTab sleeve="penny" onSleeveChange={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(en.quantLab.resultsIndexHint)).toBeInTheDocument();
    });
  });
});
