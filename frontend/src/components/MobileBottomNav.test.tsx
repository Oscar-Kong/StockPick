import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MobileBottomNav } from "@/components/MobileBottomNav";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

vi.mock("@/lib/i18n", async () => {
  const en = await import("@/lib/i18n/messages/en");
  return {
    useTranslation: () => ({ t: en.en, locale: "en" as const }),
    useLocale: () => ({ locale: "en" as const, setLocale: vi.fn() }),
  };
});

vi.mock("@/components/CommandPalette", () => ({
  openCommandPalette: vi.fn(),
}));

describe("MobileBottomNav", () => {
  afterEach(() => cleanup());

  it("renders primary destinations", () => {
    render(<MobileBottomNav />);
    const nav = screen.getByRole("navigation", { name: /mobile navigation/i });
    expect(nav).toBeTruthy();
    expect(screen.getByRole("link", { name: /portfolio/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /scan/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /analyze/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /quant lab/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /more/i })).toBeTruthy();
  });
});
