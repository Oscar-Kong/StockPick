import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { Nav } from "@/components/Nav";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

vi.mock("@/lib/i18n", async () => {
  const en = await import("@/lib/i18n/messages/en");
  return { useTranslation: () => ({ t: en.en, locale: "en" as const }) };
});

vi.mock("@/components/CommandPalette", () => ({
  CommandPalette: () => null,
  CommandPaletteTrigger: () => null,
}));

vi.mock("@/components/SettingsMenu", () => ({
  SettingsMenu: () => null,
}));

describe("Nav", () => {
  afterEach(() => cleanup());

  it("shows Portfolio as the first nav item", () => {
    render(<Nav />);
    const nav = screen.getByRole("navigation", { name: /main/i });
    const links = nav.querySelectorAll("a");
    expect(links[0]?.textContent).toBe("Portfolio");
  });

  it("does not show separate Home and Portfolio items", () => {
    render(<Nav />);
    const nav = screen.getByRole("navigation", { name: /main/i });
    const labels = [...nav.querySelectorAll("a")].map((el) => el.textContent);
    expect(labels.filter((l) => l === "Home")).toHaveLength(0);
    expect(labels.filter((l) => l === "Portfolio")).toHaveLength(1);
  });
});
