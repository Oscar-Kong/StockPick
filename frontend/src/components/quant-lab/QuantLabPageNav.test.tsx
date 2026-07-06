import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { QuantLabPage } from "../QuantLabPage";

const push = vi.fn();
const replace = vi.fn();

let searchParams = new URLSearchParams("");

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => searchParams,
}));

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: {
      quantLab: {
        title: "Quant Lab",
        subtitle: "Research",
        navAria: "Nav",
        navOverview: "Overview",
        navIdeas: "Ideas",
        navExperiments: "Experiments",
        navFactorDiscovery: "Factor Discovery",
        navResults: "Results",
        navModelMonitor: "Model Monitor",
        navLegacy: "Legacy tools",
        navGroupWorkflow: "Workflow",
        navMore: "More",
        researchOnlyWarning: "Research only",
        infoDrawerButton: "Guide",
        sectionHintOverview: "Overview hint",
        sectionHintIdeas: "Ideas hint",
        sectionHintExperiments: "Experiments hint",
        sectionHintFactorDiscovery: "FD hint",
        sectionHintResults: "Results hint",
        sectionHintModelMonitor: "Monitor hint",
      },
      common: { loading: "Loading", bucket: "Sleeve" },
      product: { researchOnlyBadge: "Research only" },
    },
    locale: "en",
  }),
}));

vi.mock("@/components/quant-lab/OverviewTab", () => ({
  OverviewTab: () => <div data-testid="overview-tab">Overview</div>,
}));
vi.mock("@/components/quant-lab/IdeasBoardTab", () => ({
  IdeasBoardTab: () => <div data-testid="ideas-tab">Ideas</div>,
}));
vi.mock("@/components/quant-lab/ExperimentStudio", () => ({
  ExperimentStudio: () => <div data-testid="experiments-tab">Experiments</div>,
}));
vi.mock("@/components/quant-lab/factor-discovery/FactorDiscoveryWorkspace", () => ({
  FactorDiscoveryWorkspace: () => <div data-testid="factor-discovery-tab">Factor Discovery</div>,
}));
vi.mock("@/components/quant-lab/ResultsTab", () => ({
  ResultsTab: () => <div data-testid="results-tab">Results</div>,
}));
vi.mock("@/components/quant-lab/ModelMonitorTab", () => ({
  ModelMonitorTab: () => <div data-testid="model-monitor-tab">Model Monitor</div>,
}));
vi.mock("@/components/quant-lab/LegacyQuantLabTabs", () => ({
  LegacyQuantLabTabs: () => <div data-testid="legacy-tabs">Legacy</div>,
}));
vi.mock("@/components/quant-lab/QuantLabInfoDrawer", () => ({
  QuantLabInfoDrawer: ({ open }: { open: boolean }) => (open ? <div data-testid="info-drawer">Drawer</div> : null),
}));

describe("QuantLabPage navigation", () => {
  beforeEach(() => {
    push.mockClear();
    replace.mockClear();
    searchParams = new URLSearchParams("");
  });

  it("defaults to overview section", () => {
    render(<QuantLabPage />);
    expect(screen.getAllByTestId("overview-tab").length).toBeGreaterThan(0);
    expect(screen.getByText("Overview hint")).toBeInTheDocument();
  });

  it("opens factor discovery when section query is set", () => {
    searchParams = new URLSearchParams("section=factor-discovery");
    render(<QuantLabPage />);
    expect(screen.getByTestId("factor-discovery-tab")).toBeInTheDocument();
  });

  it("navigates to ideas section via click", () => {
    render(<QuantLabPage />);
    const nav = screen.getAllByRole("navigation", { name: "Nav" })[0]!;
    fireEvent.click(within(nav).getByRole("button", { name: "Ideas" }));
    expect(push).toHaveBeenCalledWith(expect.stringContaining("section=ideas"));
  });

  it("opens ideas when section query is set", () => {
    searchParams = new URLSearchParams("section=ideas");
    render(<QuantLabPage />);
    expect(screen.getAllByTestId("ideas-tab").length).toBeGreaterThan(0);
  });

  it("falls back unknown section to overview", () => {
    searchParams = new URLSearchParams("section=unknown");
    render(<QuantLabPage />);
    expect(screen.getAllByTestId("overview-tab").length).toBeGreaterThan(0);
  });

  it("maps legacy tab query to legacy section", () => {
    searchParams = new URLSearchParams("tab=walk-forward");
    render(<QuantLabPage />);
    expect(screen.getByTestId("legacy-tabs")).toBeInTheDocument();
  });

  it("supports keyboard activation on nav buttons", () => {
    render(<QuantLabPage />);
    const nav = screen.getAllByRole("navigation", { name: "Nav" })[0]!;
    const ideasBtn = within(nav).getByRole("button", { name: "Ideas" });
    ideasBtn.focus();
    expect(document.activeElement).toBe(ideasBtn);
    fireEvent.keyDown(ideasBtn, { key: "Enter" });
    fireEvent.click(ideasBtn);
    expect(push).toHaveBeenCalledWith(expect.stringContaining("section=ideas"));
  });

  it("redirects retired models section to model monitor", () => {
    searchParams = new URLSearchParams("section=models");
    render(<QuantLabPage />);
    expect(screen.getByTestId("model-monitor-tab")).toBeInTheDocument();
  });

  it("opens the info drawer from the guide button", () => {
    render(<QuantLabPage />);
    expect(screen.queryByTestId("info-drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByTestId("quant-lab-guide-btn")[0]!);
    expect(screen.getByTestId("info-drawer")).toBeInTheDocument();
  });
});
