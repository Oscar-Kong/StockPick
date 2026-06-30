import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AsyncStateShell } from "./AsyncStateShell";
import { MetricTile } from "./MetricTile";

vi.mock("@/lib/i18n", async () => {
  const en = await import("@/lib/i18n/messages/en");
  return {
    useTranslation: () => ({ t: en.en, locale: "en" as const }),
  };
});

describe("AsyncStateShell", () => {
  it("renders error state with message", () => {
    render(<AsyncStateShell state="error" errorMessage="Failed to load" />);
    expect(screen.getByText("Failed to load")).toBeTruthy();
  });

  it("renders children on success", () => {
    render(
      <AsyncStateShell state="success">
        <span>Loaded data</span>
      </AsyncStateShell>
    );
    expect(screen.getByText("Loaded data")).toBeTruthy();
  });
});

describe("MetricTile", () => {
  it("renders compact variant label and value", () => {
    render(<MetricTile label="Total" value="$100" variant="compact" />);
    expect(screen.getByText("Total")).toBeTruthy();
    expect(screen.getByText("$100")).toBeTruthy();
  });
});
