import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const getHealthMock = vi.fn();

vi.mock("@/lib/api", () => ({
  getHealth: (...args: unknown[]) => getHealthMock(...args),
}));

vi.mock("@/lib/dismissedNotices", () => ({
  subscribeDismissedNotices: () => () => {},
  getDismissedNoticesSnapshot: () => new Set<string>(),
  EMPTY_DISMISSED_NOTICES: new Set<string>(),
  dismissNotice: vi.fn(),
  notifyDismissedNoticesChanged: vi.fn(),
}));

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: {
      demo: {
        publicPill: "Demo",
        publicBanner: "Demo environment banner text.",
      },
      common: { close: "Close" },
    },
  }),
}));

import { PublicDemoBanner } from "./PublicDemoBanner";

describe("PublicDemoBanner", () => {
  beforeEach(() => {
    getHealthMock.mockReset();
  });

  it("shows banner when health reports demo_mode", async () => {
    getHealthMock.mockResolvedValue({
      status: "ok",
      demo_mode: true,
      environment: "production",
      database: "available",
      version: "1.1.0",
    });

    render(<PublicDemoBanner />);
    expect(await screen.findByText("Demo environment banner text.")).toBeTruthy();
  });

  it("hides banner when not in demo mode", async () => {
    getHealthMock.mockResolvedValue({
      status: "ok",
      demo_mode: false,
    });

    const { container } = render(<PublicDemoBanner />);
    await vi.waitFor(() => {
      expect(getHealthMock).toHaveBeenCalled();
    });
    expect(container.textContent).toBe("");
  });
});
