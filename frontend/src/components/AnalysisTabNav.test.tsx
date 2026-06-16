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
  {
    id: "overview",
    label: "Overview",
    shortLabel: "Ovw",
    hint: "Overview hint",
    group: "core",
  },
  {
    id: "score",
    label: "Score",
    shortLabel: "Score",
    hint: "Score hint",
    group: "core",
  },
];

describe("AnalysisTabNav", () => {
  afterEach(() => cleanup());

  it("shows active tab hint and switches tabs", () => {
    const onChange = vi.fn();
    render(
      <AnalysisTabNav tabs={tabs} active="overview" onChange={onChange} ariaLabel="Views" />
    );
    expect(screen.getByText("Overview hint")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("Score hint"));
    expect(onChange).toHaveBeenCalledWith("score");
  });
});
