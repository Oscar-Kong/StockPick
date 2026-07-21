"use client";

import clsx from "clsx";
import type { DailyDashboardResponse } from "@/lib/types";
import { homeNoticeId } from "@/lib/dismissedNotices";
import { useTranslation } from "@/lib/i18n";
import { DismissibleNotice } from "@/components/ui/DismissibleNotice";

export function DataFreshnessBanner({ data }: { data: DailyDashboardResponse }) {
  const { t } = useTranslation();
  const f = data.freshness;
  if (!f) return null;

  // Cash-only MCP: no positions to decide — suppress stale/missing decision banners.
  const mcpCashOnly =
    data.data_source === "robinhood_mcp" &&
    Boolean(data.robinhood_mcp_authenticated) &&
    !(data.holdings?.length ?? 0);
  if (mcpCashOnly && (f.overall_status === "stale" || f.overall_status === "missing")) {
    return null;
  }

  const status = f.overall_status;
  if (status === "fresh" || status === "demo") return null;

  const message =
    status === "updating"
      ? t.home.dailyFreshnessUpdating
      : status === "missing"
        ? t.home.dailyFreshnessMissing
        : data.decision_stale_warning ?? t.home.dailyFreshnessStale;

  const messageKey =
    status === "updating" ? "updating" : status === "missing" ? "missing" : data.decision_stale_warning ?? "stale";

  const tone =
    status === "updating"
      ? "border-sky-500/25 bg-sky-500/8 text-sky-100"
      : status === "missing"
        ? "border-amber-500/25 bg-amber-500/8 text-amber-100"
        : "border-amber-500/20 bg-amber-500/5 text-zinc-300";

  return (
    <DismissibleNotice
      noticeId={homeNoticeId.freshness(status, messageKey)}
      className={clsx("rounded-xl border px-4 py-3 text-sm leading-relaxed", tone)}
    >
      {message}
    </DismissibleNotice>
  );
}
