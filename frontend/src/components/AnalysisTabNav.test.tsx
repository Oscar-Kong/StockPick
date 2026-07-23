import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { AnalysisTabNav, analysisPanelId, type AnalysisTabConfig } from "./AnalysisTabNav";

const tabs: AnalysisTabConfig[] = [
  { id: "overview", label: "Overview", shortLabel: "Ovw", hint: "Overview hint" },
  { id: "drivers", label: "Drivers", shortLabel: "Drv", hint: "Drivers hint" },
  { id: "research", label: "Research", shortLabel: "Rpt", hint: "Research hint" },
];

describe("AnalysisTabNav", () => {
  afterEach(() => cleanup());

  it("renders a flat underline tablist without group headings", () => {
    const onChange = vi.fn();
    render(
      <AnalysisTabNav tabs={tabs} active="overview" onChange={onChange} ariaLabel="Views" />
    );
    expect(screen.queryByText("Core")).not.toBeInTheDocument();
    expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
    expect(screen.queryByText("Overview hint")).not.toBeInTheDocument();
    const overviewTab = screen.getByRole("tab", { name: "Overview" });
    expect(overviewTab).toHaveAttribute("aria-selected", "true");
    expect(overviewTab).toHaveAttribute("aria-controls", analysisPanelId("overview"));
    expect(overviewTab).toHaveClass("analysis-tab--active");
    expect(screen.getAllByRole("tab")).toHaveLength(3);
    fireEvent.click(screen.getByRole("tab", { name: "Drivers" }));
    expect(onChange).toHaveBeenCalledWith("drivers");
  });
});
