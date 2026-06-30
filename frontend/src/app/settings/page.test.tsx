import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";

const replaceMock = vi.fn();
const backMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, back: backMock, push: vi.fn() }),
  useSearchParams: () => new URLSearchParams("section=language"),
}));

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
}));

vi.mock("@/components/LanguageSettingsPanel", () => ({
  LanguageSettingsPanel: () => <div>Language panel</div>,
}));
vi.mock("@/components/quant/QuantHealthCard", () => ({
  QuantHealthCard: () => <div>Quant health panel</div>,
}));
vi.mock("@/components/settings/ThemeSettingsPanel", () => ({
  ThemeSettingsPanel: () => <div>Theme panel</div>,
}));
vi.mock("@/components/settings/MorningScanEmailPanel", () => ({
  MorningScanEmailPanel: () => <div>Ops panel</div>,
}));
vi.mock("@/components/ApiSettingsPanel", () => ({
  ApiSettingsPanel: () => <div>API panel</div>,
}));

import SettingsPage from "@/app/settings/page";

describe("SettingsPage", () => {
  afterEach(() => {
    cleanup();
    replaceMock.mockClear();
  });

  it("shows language section by default from query param", () => {
    render(<SettingsPage />);
    expect(screen.getByText("Language panel")).toBeInTheDocument();
    expect(screen.queryByText("API panel")).not.toBeInTheDocument();
  });

  it("navigates sections via sidebar click", () => {
    render(<SettingsPage />);
    fireEvent.click(screen.getByRole("button", { name: en.settings.sectionApi }));
    expect(replaceMock).toHaveBeenCalledWith("/settings?section=api");
  });
});
