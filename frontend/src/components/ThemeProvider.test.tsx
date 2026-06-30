import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeProvider, useTheme } from "@/components/ThemeProvider";
import { THEME_STORAGE_KEY } from "@/lib/theme";

function TestConsumer() {
  const { preference, resolved } = useTheme();
  return (
    <div>
      <span data-testid="pref">{preference}</span>
      <span data-testid="resolved">{resolved}</span>
    </div>
  );
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.setAttribute("data-theme", "dark");
  });

  it("defaults to dark theme", () => {
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    );
    expect(screen.getByTestId("pref")).toHaveTextContent("dark");
    expect(screen.getByTestId("resolved")).toHaveTextContent("dark");
  });

  it("persists light preference", () => {
    function Picker() {
      const { setPreference } = useTheme();
      return (
        <button type="button" onClick={() => setPreference("light")}>
          Light
        </button>
      );
    }
    render(
      <ThemeProvider>
        <Picker />
        <TestConsumer />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByRole("button", { name: "Light" }));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
