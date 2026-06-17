const STORAGE_KEY = "picker-home-dismissed";

/** Stable empty set for SSR and empty storage. */
export const EMPTY_DISMISSED_NOTICES = new Set<string>();

let snapshotCache: Set<string> = EMPTY_DISMISSED_NOTICES;
let snapshotRaw = "";

function parseStored(raw: string | null): Set<string> {
  if (!raw) return EMPTY_DISMISSED_NOTICES;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return EMPTY_DISMISSED_NOTICES;
    const ids = parsed.filter((id): id is string => typeof id === "string");
    if (!ids.length) return EMPTY_DISMISSED_NOTICES;
    return new Set(ids);
  } catch {
    return EMPTY_DISMISSED_NOTICES;
  }
}

/** Stable snapshot for useSyncExternalStore — same reference until storage changes. */
export function getDismissedNoticesSnapshot(): Set<string> {
  if (typeof window === "undefined") return EMPTY_DISMISSED_NOTICES;
  const raw = localStorage.getItem(STORAGE_KEY) ?? "";
  if (raw === snapshotRaw) return snapshotCache;
  snapshotRaw = raw;
  snapshotCache = parseStored(raw || null);
  return snapshotCache;
}

function commitDismissed(ids: Iterable<string>): void {
  const sorted = [...ids].sort();
  const nextRaw = JSON.stringify(sorted);
  if (nextRaw === snapshotRaw) return;
  snapshotRaw = nextRaw;
  snapshotCache = sorted.length ? new Set(sorted) : EMPTY_DISMISSED_NOTICES;
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, nextRaw);
  }
}

export const homeNoticeId = {
  portfolioWarning: (message: string) => `portfolio:${message}`,
  freshness: (status: string, message: string) => `freshness:${status}:${message}`,
  demo: () => "demo-banner",
  riskAlert: (alert: string) => `risk:${alert}`,
};

export function readDismissedNotices(): Set<string> {
  return getDismissedNoticesSnapshot();
}

export function writeDismissedNotices(ids: Iterable<string>): void {
  commitDismissed(ids);
}

export function dismissNotice(noticeId: string): void {
  const next = new Set(getDismissedNoticesSnapshot());
  if (next.has(noticeId)) return;
  next.add(noticeId);
  commitDismissed(next);
}

export function notifyDismissedNoticesChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("home-notices-changed"));
  }
}

/** Drop dismissals for notices that are no longer active (condition resolved). */
export function pruneDismissedNotices(activeIds: string[]): void {
  const active = new Set(activeIds);
  const kept = [...getDismissedNoticesSnapshot()].filter((id) => active.has(id));
  commitDismissed(kept);
}

export function activeHomeNoticeIds(data: {
  portfolio_warnings?: string[];
  is_demo_data?: boolean;
  risk_alerts?: string[];
  freshness?: { overall_status?: string } | null;
  decision_stale_warning?: string | null;
}): string[] {
  const ids: string[] = [];
  for (const w of data.portfolio_warnings ?? []) {
    ids.push(homeNoticeId.portfolioWarning(w));
  }
  const f = data.freshness;
  const status = f?.overall_status;
  if (f && status && status !== "fresh" && status !== "demo") {
    const message =
      status === "updating"
        ? "updating"
        : status === "missing"
          ? "missing"
          : data.decision_stale_warning ?? "stale";
    ids.push(homeNoticeId.freshness(status, message));
  }
  if (data.is_demo_data) {
    ids.push(homeNoticeId.demo());
  }
  for (const a of data.risk_alerts ?? []) {
    ids.push(homeNoticeId.riskAlert(a));
  }
  return ids;
}

export function subscribeDismissedNotices(onStoreChange: () => void): () => void {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener("home-notices-changed", onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener("home-notices-changed", onStoreChange);
  };
}
