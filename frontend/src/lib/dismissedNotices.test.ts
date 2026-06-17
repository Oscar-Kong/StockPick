import { describe, expect, it, beforeEach } from "vitest";
import {
  activeHomeNoticeIds,
  dismissNotice,
  getDismissedNoticesSnapshot,
  homeNoticeId,
  pruneDismissedNotices,
  readDismissedNotices,
  writeDismissedNotices,
} from "./dismissedNotices";

describe("dismissedNotices", () => {
  beforeEach(() => {
    writeDismissedNotices([]);
  });

  it("dismisses and reads notices", () => {
    dismissNotice(homeNoticeId.demo());
    expect(readDismissedNotices().has(homeNoticeId.demo())).toBe(true);
  });

  it("returns stable snapshot reference until storage changes", () => {
    const a = getDismissedNoticesSnapshot();
    const b = getDismissedNoticesSnapshot();
    expect(a).toBe(b);
    dismissNotice(homeNoticeId.demo());
    const c = getDismissedNoticesSnapshot();
    expect(c).not.toBe(a);
    expect(c.has(homeNoticeId.demo())).toBe(true);
  });

  it("prunes stale dismissals when warnings resolve", () => {
    dismissNotice(homeNoticeId.portfolioWarning("old warning"));
    dismissNotice(homeNoticeId.demo());
    pruneDismissedNotices([homeNoticeId.demo()]);
    const set = readDismissedNotices();
    expect(set.has(homeNoticeId.demo())).toBe(true);
    expect(set.has(homeNoticeId.portfolioWarning("old warning"))).toBe(false);
  });

  it("builds active notice ids from dashboard shape", () => {
    const ids = activeHomeNoticeIds({
      portfolio_warnings: ["Upload CSV"],
      is_demo_data: true,
      risk_alerts: ["AAPL: high risk"],
      freshness: { overall_status: "stale" },
      decision_stale_warning: "stale msg",
    });
    expect(ids).toContain(homeNoticeId.portfolioWarning("Upload CSV"));
    expect(ids).toContain(homeNoticeId.demo());
    expect(ids).toContain(homeNoticeId.riskAlert("AAPL: high risk"));
    expect(ids.some((id) => id.startsWith("freshness:"))).toBe(true);
  });
});
