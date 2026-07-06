import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { OverviewTab } from "./OverviewTab";
import { IdeasBoardTab } from "./IdeasBoardTab";
import * as api from "@/lib/api";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}));

const tRef = { current: en };

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
  useTRef: () => tRef,
}));

vi.mock("@/lib/api", () => ({
  getResearchOverview: vi.fn(),
  generateResearchIdeas: vi.fn(),
  listResearchIdeas: vi.fn(),
  createResearchIdea: vi.fn(),
  updateResearchIdea: vi.fn(),
  duplicateResearchIdea: vi.fn(),
  createResearchExperiment: vi.fn(),
  postIcPanelJob: vi.fn(),
  postForwardLabelsJob: vi.fn(),
  postResolveOutcomesJob: vi.fn(),
  postResearchRunsBackfill: vi.fn(),
  enqueueV2Job: vi.fn(),
}));

const mocked = vi.mocked(api);

const sampleOverview = {
  generated_at: "2026-06-20T12:00:00",
  sleeve: "penny",
  research_confidence_status: "usable_with_warnings",
  research_confidence_score: 72,
  data_freshness: "fresh",
  strategy_version: "v1",
  factor_model_version: "fv1",
  predictions_resolved: 5,
  predictions_unresolved: 2,
  failed_or_blocked_jobs: 0,
  major_warnings: [],
  findings: [
    {
      finding_id: "f1",
      title: "IC drift detected",
      explanation: "Momentum IC changed",
      supporting_metric: "delta=0.05",
      source_reference: "factor_ic",
      why_it_matters: "Review weights",
      confidence: 0.8,
      evidence_impact: "informational",
      suggested_experiment_type: "factor_validation",
      suggested_parameters: {},
    },
  ],
  recommended_ideas: [],
  recent_activity: [],
  maintenance_actions: [
    {
      action_id: "refresh_evidence",
      label: "Refresh evidence index",
      description: "Backfill",
      endpoint: "/api/v2/research/runs/backfill",
      method: "POST",
      available: true,
    },
  ],
};

const sampleIdea = {
  id: "idea_1",
  title: "Test idea",
  hypothesis: "Hypothesis text",
  description: "",
  why_now: "metric",
  source_type: "user_created" as const,
  source_references: [],
  sleeve: "penny",
  universe_definition: {},
  suggested_experiment_type: "walk_forward",
  suggested_parameters: {},
  priority: 80,
  confidence: 0.7,
  status: "new" as const,
  user_notes: "",
  created_at: "2026-06-20",
  updated_at: "2026-06-20",
};

describe("OverviewTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocked.getResearchOverview.mockResolvedValue(sampleOverview);
  });

  afterEach(() => cleanup());

  it("renders overview confidence on load", async () => {
    render(<OverviewTab sleeve="penny" onOpenIdeas={() => undefined} />);
    await waitFor(() => expect(screen.getByText(/72\/100/)).toBeInTheDocument());
    expect(screen.getByText(/Today's research brief/i)).toBeInTheDocument();
    expect(mocked.getResearchOverview).toHaveBeenCalledWith("penny");
  });

  it("shows empty findings copy when none", async () => {
    mocked.getResearchOverview.mockResolvedValue({ ...sampleOverview, findings: [] });
    render(<OverviewTab sleeve="penny" onOpenIdeas={() => undefined} />);
    await waitFor(() => expect(screen.getByText(/No deterministic findings/i)).toBeInTheDocument());
  });

  it("renders research brief finding details", async () => {
    render(<OverviewTab sleeve="penny" onOpenIdeas={() => undefined} />);
    await waitFor(() => expect(screen.getByText("IC drift detected")).toBeInTheDocument());
    expect(screen.getByText("delta=0.05")).toBeInTheDocument();
  });

  it("shows error state on load failure", async () => {
    mocked.getResearchOverview.mockRejectedValue(new Error("network"));
    render(<OverviewTab sleeve="penny" onOpenIdeas={() => undefined} />);
    await waitFor(() => expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument());
  });

  it("shows partial failure banner after maintenance error", async () => {
    mocked.postResearchRunsBackfill.mockRejectedValue(new Error("job failed"));
    render(<OverviewTab sleeve="penny" onOpenIdeas={() => undefined} />);
    await waitFor(() => screen.getByText(/Evidence maintenance/i));
    fireEvent.click(screen.getByText("Evidence maintenance"));
    const runBtn = await screen.findByRole("button", { name: /^Run$/i });
    fireEvent.click(runBtn);
    await waitFor(() => expect(screen.getByText(/job failed|failed/i)).toBeInTheDocument());
    expect(screen.getByText(/72\/100/)).toBeInTheDocument();
  });

  it("runs maintenance action", async () => {
    mocked.postResearchRunsBackfill.mockResolvedValue({ indexed: 1 });
    render(<OverviewTab sleeve="penny" onOpenIdeas={() => undefined} />);
    await waitFor(() => screen.getByText(/Evidence maintenance/i));
    fireEvent.click(screen.getByText("Evidence maintenance"));
    const runBtn = await screen.findByRole("button", { name: /^Run$/i });
    fireEvent.click(runBtn);
    await waitFor(() => expect(mocked.postResearchRunsBackfill).toHaveBeenCalled());
  });

  it("generates ideas and opens ideas section", async () => {
    const onOpenIdeas = vi.fn();
    mocked.generateResearchIdeas.mockResolvedValue({ created: [], skipped_duplicates: 0, findings_used: 1 });
    render(<OverviewTab sleeve="penny" onOpenIdeas={onOpenIdeas} />);
    await waitFor(() => screen.getByText(/Generate ideas from brief/i));
    fireEvent.click(screen.getByText(/Generate ideas from brief/i));
    await waitFor(() => expect(mocked.generateResearchIdeas).toHaveBeenCalled());
    expect(onOpenIdeas).toHaveBeenCalled();
  });
});

describe("IdeasBoardTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPush.mockClear();
    mocked.listResearchIdeas.mockResolvedValue({ ideas: [sampleIdea], total: 1, offset: 0, limit: 100 });
  });

  afterEach(() => cleanup());

  it("lists ideas", async () => {
    render(<IdeasBoardTab sleeve="penny" onSleeveChange={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Test idea")).toBeInTheDocument());
  });

  it("creates manual idea", async () => {
    mocked.createResearchIdea.mockResolvedValue(sampleIdea);
    render(<IdeasBoardTab sleeve="penny" onSleeveChange={() => undefined} />);
    await waitFor(() => screen.getByText("New idea"));
    fireEvent.click(screen.getByText("New idea"));
    fireEvent.change(screen.getByPlaceholderText("Idea title"), { target: { value: "Manual" } });
    fireEvent.click(screen.getByText("Save idea"));
    await waitFor(() => expect(mocked.createResearchIdea).toHaveBeenCalled());
  });

  it("generates ideas from board", async () => {
    mocked.generateResearchIdeas.mockResolvedValue({ created: [sampleIdea], skipped_duplicates: 0, findings_used: 1 });
    render(<IdeasBoardTab sleeve="penny" onSleeveChange={() => undefined} />);
    await waitFor(() => screen.getByText(/Generate ideas from brief/i));
    fireEvent.click(screen.getByText(/Generate ideas from brief/i));
    await waitFor(() => expect(mocked.generateResearchIdeas).toHaveBeenCalled());
  });

  it("edits idea notes and priority", async () => {
    mocked.updateResearchIdea.mockResolvedValue({ ...sampleIdea, user_notes: "note", priority: 90 });
    render(<IdeasBoardTab sleeve="penny" onSleeveChange={() => undefined} />);
    await waitFor(() => screen.getByText("Edit"));
    fireEvent.click(screen.getByText("Edit"));
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "note" } });
    fireEvent.click(screen.getByText("Save changes"));
    await waitFor(() =>
      expect(mocked.updateResearchIdea).toHaveBeenCalledWith(
        "idea_1",
        expect.objectContaining({ user_notes: "note" })
      )
    );
  });

  it("archives idea", async () => {
    mocked.updateResearchIdea.mockResolvedValue({ ...sampleIdea, status: "archived" });
    render(<IdeasBoardTab sleeve="penny" onSleeveChange={() => undefined} />);
    await waitFor(() => screen.getByText("Archive"));
    fireEvent.click(screen.getByText("Archive"));
    await waitFor(() => expect(mocked.updateResearchIdea).toHaveBeenCalled());
  });

  it("duplicates idea", async () => {
    mocked.duplicateResearchIdea.mockResolvedValue({ ...sampleIdea, id: "idea_2", title: "Test idea (copy)" });
    render(<IdeasBoardTab sleeve="penny" onSleeveChange={() => undefined} />);
    await waitFor(() => screen.getByText("Duplicate"));
    fireEvent.click(screen.getByText("Duplicate"));
    await waitFor(() => expect(mocked.duplicateResearchIdea).toHaveBeenCalledWith("idea_1"));
  });

  it("navigates to experiment from idea", async () => {
    mocked.createResearchExperiment.mockResolvedValue({ id: "exp_1" } as never);
    mocked.updateResearchIdea.mockResolvedValue({ ...sampleIdea, status: "ready_to_test" });
    render(<IdeasBoardTab sleeve="penny" onSleeveChange={() => undefined} />);
    await waitFor(() => screen.getByText("Configure experiment"));
    fireEvent.click(screen.getByText("Configure experiment"));
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith(expect.stringContaining("section=experiments"))
    );
    expect(mockPush).toHaveBeenCalledWith(expect.stringContaining("experiment=exp_1"));
  });
});
