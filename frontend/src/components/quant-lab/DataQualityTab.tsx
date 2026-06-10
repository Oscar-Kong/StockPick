"use client";

import { QuantHealthCard } from "@/components/quant/QuantHealthCard";
import { getQuantHealthSummary, getSchedulerStatus } from "@/lib/api";
import { countFailedSchedulerJobs } from "@/lib/quantLabStability";
import { computeDataQualityReliability } from "@/lib/researchReliability";
import type { QuantHealthSummary, SchedulerStatusResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { useCallback, useEffect, useMemo, useState } from "react";
import { QuantLabEmptyState, QuantLabTabLayout, TabRefreshRow } from "./QuantLabTabShell";
import { ResearchReliabilityCard } from "./ResearchReliabilityCard";

export function DataQualityTab() {
  const { t } = useTranslation();
  const [health, setHealth] = useState<QuantHealthSummary | null>(null);
  const [scheduler, setScheduler] = useState<SchedulerStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [h, s] = await Promise.allSettled([getQuantHealthSummary(), getSchedulerStatus()]);
    setHealth(h.status === "fulfilled" ? h.value : null);
    setScheduler(s.status === "fulfilled" ? s.value : null);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const failedJobCount = countFailedSchedulerJobs(scheduler?.recent_jobs ?? []);
  const reliability = useMemo(
    () => computeDataQualityReliability({ health, scheduler, failedJobCount, loading }),
    [health, scheduler, failedJobCount, loading]
  );

  return (
    <QuantLabTabLayout
      title={t.quantLab.tabDataQuality}
      description={t.quantLab.hintDataQuality}
      reliability={<ResearchReliabilityCard score={reliability} />}
    >
      <QuantHealthCard embedded />
      <SchedulerPanel scheduler={scheduler} loading={loading} onRefresh={load} failedJobCount={failedJobCount} />
    </QuantLabTabLayout>
  );
}

function SchedulerPanel({
  scheduler,
  loading,
  onRefresh,
  failedJobCount,
}: {
  scheduler: SchedulerStatusResponse | null;
  loading: boolean;
  onRefresh: () => void;
  failedJobCount: number;
}) {
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !scheduler) {
      setError(t.settings.schedulerUnavailable);
    } else {
      setError(null);
    }
  }, [loading, scheduler]);

  const jobs = scheduler?.recent_jobs ?? [];

  return (
    <div className="surface-card p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-200">{t.settings.schedulerTitle}</h3>
        <TabRefreshRow onRefresh={onRefresh} />
      </div>
      {loading && <p className="text-xs text-zinc-500">{t.common.loading}</p>}
      {error && (
        <p className="text-xs text-amber-300">
          {t.quantLab.schedulerUnavailableWarning}: {error}
        </p>
      )}
      {!loading && scheduler && (
        <>
          <p className="text-xs text-zinc-500">
            {scheduler.enabled ? t.settings.schedulerOn : t.settings.schedulerOff}
          </p>
          {failedJobCount > 0 && (
            <p className="text-xs text-amber-300">
              {t.quantLab.schedulerFailedJobs.replace("{count}", String(failedJobCount))}
            </p>
          )}
          {jobs.length === 0 ? (
            <QuantLabEmptyState message={t.quantLab.noSchedulerJobs} />
          ) : (
            <ul className="space-y-1 text-xs text-zinc-400">
              {jobs.slice(0, 5).map((j, i) => (
                <li key={`${j.job_name}-${i}`}>
                  {j.job_name}: {j.status} {j.message ? `— ${j.message}` : ""}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {!loading && !scheduler && !error && (
        <p className="text-xs text-zinc-500">{t.settings.schedulerUnavailable}</p>
      )}
    </div>
  );
}
