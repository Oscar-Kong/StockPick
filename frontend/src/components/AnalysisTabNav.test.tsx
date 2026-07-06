import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { AnalysisTabNav, analysisPanelId, type AnalysisTabConfig } from "./AnalysisTabNav";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
  fmt: (template: string, vars: Record<string, string | number>) =>
    template.replace(/\{(\w+)\}/g, (_, key) => String(vars[key] ?? "")),
}));

const tabs: AnalysisTabConfig[] = [
  { id: "overview", label: "Overview", shortLabel: "Ovw", hint: "Overview hint", group: "core" },
  { id: "score", label: "Score", shortLabel: "Score", hint: "Score hint", group: "core" },
  { id: "report", label: "AI Report", shortLabel: "Rpt", hint: "Report hint", group: "workspace" },
];

describe("AnalysisTabNav", () => {
  afterEach(() => cleanup());

  it("renders grouped underline tabs with aria-controls linkage", () => {
    const onChange = vi.fn();
    render(
      <AnalysisTabNav tabs={tabs} active="overview" onChange={onChange} ariaLabel="Views" />
    );
    expect(screen.getByText(en.analysis.tabGroupCore)).toBeInTheDocument();
    expect(screen.getByText(en.analysis.tabGroupWorkspace)).toBeInTheDocument();
    expect(screen.queryByText("Overview hint")).not.toBeInTheDocument();
    const overviewTab = screen.getByRole("tab", { name: "Overview" });
    expect(overviewTab).toHaveAttribute("aria-selected", "true");
    expect(overviewTab).toHaveAttribute("aria-controls", analysisPanelId("overview"));
    fireEvent.click(screen.getByRole("tab", { name: "Score" }));
    expect(onChange).toHaveBeenCalledWith("score");
  });
});
