import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { SettingsMenu } from "@/components/SettingsMenu";

const setLocaleMock = vi.fn();

vi.mock("@/lib/i18n", async () => {
  const en = await import("@/lib/i18n/messages/en");
  return {
    useLocale: () => ({ locale: "en" as const, setLocale: setLocaleMock, t: en.en }),
  };
});

describe("SettingsMenu", () => {
  afterEach(() => {
    cleanup();
    setLocaleMock.mockClear();
  });

  it("shows Settings label on trigger, not locale code", () => {
    render(<SettingsMenu />);
    const trigger = screen.getByRole("button", { name: "Settings" });
    expect(trigger.textContent).toContain("Settings");
    expect(trigger.textContent).not.toMatch(/\bEN\b/);
  });

  it("opens menu with all settings link and quick links", () => {
    render(<SettingsMenu />);
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));

    expect(screen.getByRole("menuitem", { name: /All settings/i })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("menuitem", { name: "Appearance" })).toHaveAttribute(
      "href",
      "/settings?section=theme"
    );
    expect(screen.getByRole("menuitem", { name: "API integrations" })).toHaveAttribute(
      "href",
      "/settings?section=api"
    );
  });
});
