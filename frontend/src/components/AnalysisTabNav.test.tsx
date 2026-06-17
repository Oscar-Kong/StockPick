import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { AnalysisTabNav, type AnalysisTabConfig } from "./AnalysisTabNav";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
  fmt: (template: string, vars: Record<string, string | number>) =>
    template.replace(/\{(\w+)\}/g, (_, key) => String(vars[key] ?? "")),
}));

const tabs: AnalysisTabConfig[] = [
  { id: "overview", label: "Overview", shortLabel: "Ovw", hint: "Overview hint" },
  { id: "score", label: "Score", shortLabel: "Score", hint: "Score hint" },
  { id: "report", label: "AI Report", shortLabel: "Rpt", hint: "Report hint" },
];

describe("AnalysisTabNav", () => {
  afterEach(() => cleanup());

  it("renders one continuous tab bar without group labels or hint row", () => {
    const onChange = vi.fn();
    render(
      <AnalysisTabNav tabs={tabs} active="overview" onChange={onChange} ariaLabel="Views" />
    );
    expect(screen.queryByText(en.analysis.tabGroupCore)).not.toBeInTheDocument();
    expect(screen.queryByText("Overview hint")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "Score" }));
    expect(onChange).toHaveBeenCalledWith("score");
  });
});
