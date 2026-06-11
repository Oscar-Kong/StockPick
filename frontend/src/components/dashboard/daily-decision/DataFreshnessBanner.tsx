"use client";

import clsx from "clsx";
import type { DailyDashboardResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";

export function DataFreshnessBanner({ data }: { data: DailyDashboardResponse }) {
  const { t } = useTranslation();
  const f = data.freshness;
  if (!f) return null;

  const status = f.overall_status;
  if (status === "fresh" || status === "demo") return null;

  const message =
    status === "updating"
      ? t.home.dailyFreshnessUpdating
      : status === "missing"
        ? t.home.dailyFreshnessMissing
        : data.decision_stale_warning ?? t.home.dailyFreshnessStale;

  const tone =
    status === "updating"
      ? "border-sky-500/25 bg-sky-500/8 text-sky-100"
      : status === "missing"
        ? "border-amber-500/25 bg-amber-500/8 text-amber-100"
        : "border-amber-500/20 bg-amber-500/5 text-zinc-300";

  return (
    <div className={clsx("rounded-xl border px-4 py-3 text-sm leading-relaxed", tone)} role="status">
      {message}
    </div>
  );
}
