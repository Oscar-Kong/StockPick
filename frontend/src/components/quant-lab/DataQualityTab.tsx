"use client";

import { QuantHealthCard } from "@/components/quant/QuantHealthCard";
import { getSchedulerStatus } from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import { countFailedSchedulerJobs } from "@/lib/quantLabStability";
import { useTranslation } from "@/lib/i18n";
import { useCallback, useEffect, useState } from "react";
import { QuantLabEmptyState, QuantLabTabLayout, TabRefreshRow } from "./QuantLabTabShell";

export function DataQualityTab() {
  const { t } = useTranslation();
  return (
    <QuantLabTabLayout
      title={t.quantLab.tabDataQuality}
      description={t.quantLab.hintDataQuality}
    >
      <QuantHealthCard embedded />
      <SchedulerPanel />
    </QuantLabTabLayout>
  );
}

function SchedulerPanel() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Awaited<ReturnType<typeof getSchedulerStatus>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getSchedulerStatus()
      .then(setStatus)
      .catch((e) => {
        setStatus(null);
        setError(parseApiError(e, t.settings.schedulerUnavailable));
      })
      .finally(() => setLoading(false));
  }, [t.settings.schedulerUnavailable]);

  useEffect(() => {
    load();
  }, [load]);

  const jobs = status?.recent_jobs ?? [];
  const failedCount = countFailedSchedulerJobs(jobs);

  return (
    <div className="surface-card p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-200">{t.settings.schedulerTitle}</h3>
        <TabRefreshRow onRefresh={load} />
      </div>
      {loading && <p className="text-xs text-zinc-500">{t.common.loading}</p>}
      {error && (
        <p className="text-xs text-amber-300">
          {t.quantLab.schedulerUnavailableWarning}: {error}
        </p>
      )}
      {!loading && status && (
        <>
          <p className="text-xs text-zinc-500">
            {status.enabled ? t.settings.schedulerOn : t.settings.schedulerOff}
          </p>
          {failedCount > 0 && (
            <p className="text-xs text-amber-300">
              {t.quantLab.schedulerFailedJobs.replace("{count}", String(failedCount))}
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
      {!loading && !status && !error && (
        <p className="text-xs text-zinc-500">{t.settings.schedulerUnavailable}</p>
      )}
    </div>
  );
}
