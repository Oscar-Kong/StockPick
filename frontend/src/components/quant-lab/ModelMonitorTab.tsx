"use client";

import {
  getModelMonitor,
  getV2Audit,
  listEvidenceReview,
  postEvidenceReviewAction,
  retryResearchJob,
} from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import type { Bucket, ModelMonitorResponse } from "@/lib/types";
import { buildQuantLabHref } from "@/lib/quantLabNavigation";
import { useTranslation, useTRef } from "@/lib/i18n";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { BucketSelect } from "./QuantLabTabShell";
import { DataQualityTab } from "./DataQualityTab";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ApplyChangesNotice } from "@/components/product/ApplyChangesNotice";

type MonitorSection =
  | "factor"
  | "prediction"
  | "data"
  | "jobs"
  | "config"
  | "audit"
  | "evidence-review";

interface ModelMonitorTabProps {
  sleeve: Bucket;
  onSleeveChange: (sleeve: Bucket) => void;
}

export function ModelMonitorTab({ sleeve, onSleeveChange }: ModelMonitorTabProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const router = useRouter();
  const [section, setSection] = useState<MonitorSection>("factor");
  const [data, setData] = useState<ModelMonitorResponse | null>(null);
  const [auditEvents, setAuditEvents] = useState<Array<Record<string, unknown>>>([]);
  const [review, setReview] = useState<Awaited<ReturnType<typeof listEvidenceReview>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [mon, aud, rev] = await Promise.allSettled([
        getModelMonitor(sleeve),
        getV2Audit({ limit: 20, sleeve }),
        listEvidenceReview({ sleeve, limit: 30 }),
      ]);
      setData(mon.status === "fulfilled" ? mon.value : null);
      setAuditEvents(aud.status === "fulfilled" ? aud.value.events ?? [] : []);
      setReview(rev.status === "fulfilled" ? rev.value : null);
      if (mon.status === "rejected") {
        setError(parseApiError(mon.reason, tRef.current.quantLab.loadFailed));
      }
    } finally {
      setLoading(false);
    }
  }, [sleeve, tRef]);

  useEffect(() => {
    void load();
  }, [load]);

  const sections: { id: MonitorSection; label: string }[] = [
    { id: "factor", label: t.quantLab.monitorFactorHealth },
    { id: "prediction", label: t.quantLab.monitorPredictionHealth },
    { id: "data", label: t.quantLab.monitorDataHealth },
    { id: "jobs", label: t.quantLab.monitorResearchJobs },
    { id: "config", label: t.quantLab.monitorModelConfig },
    { id: "audit", label: t.quantLab.monitorAudit },
    { id: "evidence-review", label: t.quantLab.monitorEvidenceReview },
  ];

  const openRun = (runId: string) => {
    router.push(buildQuantLabHref("results", { extra: { run_id: runId } }));
  };

  const onReviewAction = async (findingId: string, action: string) => {
    setBusy(findingId);
    try {
      await postEvidenceReviewAction(findingId, { action, notes: "" });
      await load();
    } catch (e) {
      setError(parseApiError(e, tRef.current.quantLab.runFailed));
    } finally {
      setBusy(null);
    }
  };

  const onRetryJob = async (jobId: string) => {
    setBusy(jobId);
    try {
      await retryResearchJob(jobId);
      await load();
    } catch (e) {
      setError(parseApiError(e, tRef.current.quantLab.runFailed));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-3 text-sm">
      <p className="text-zinc-400">{t.quantLab.monitorHint}</p>
      <div className="flex flex-wrap items-end gap-2">
        <BucketSelect sleeve={sleeve} onChange={onSleeveChange} />
        <button type="button" className="rounded border border-zinc-700 px-2 py-1 text-xs" onClick={() => void load()}>
          {t.common.refresh}
        </button>
      </div>

      <div className="flex flex-wrap gap-1">
        {sections.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`rounded-full border px-2 py-0.5 text-xs ${
              section === s.id ? "border-sky-600 bg-sky-950/40 text-sky-200" : "border-zinc-700 text-zinc-400"
            }`}
            onClick={() => setSection(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>

      {error && <ErrorState message={error} onRetry={() => void load()} />}
      {loading && <LoadingSkeleton lines={8} />}

      {!loading && data && section === "factor" && (
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="min-w-full text-xs">
            <thead className="bg-zinc-900/80 text-zinc-400">
              <tr>
                <th className="px-2 py-2 text-left">{t.quantLab.monitorFactorName}</th>
                <th className="px-2 py-2 text-left">{t.quantLab.monitorLifecycle}</th>
                <th className="px-2 py-2 text-left">{t.quantLab.monitorWeight}</th>
                <th className="px-2 py-2 text-left">{t.quantLab.monitorRecentIc}</th>
                <th className="px-2 py-2 text-left">{t.quantLab.monitorDrift}</th>
                <th className="px-2 py-2 text-left">{t.quantLab.monitorEvidence}</th>
              </tr>
            </thead>
            <tbody>
              {data.factor_health.map((f) => (
                <tr key={f.factor_id} className="border-t border-zinc-800">
                  <td className="px-2 py-2 text-zinc-200">{f.display_name}</td>
                  <td className="px-2 py-2">{f.lifecycle}</td>
                  <td className="px-2 py-2 tabular-nums">{f.production_weight ?? "—"}</td>
                  <td className="px-2 py-2 tabular-nums">{f.recent_ic ?? "—"}</td>
                  <td className="px-2 py-2 tabular-nums">{f.drift ?? "—"}</td>
                  <td className="px-2 py-2">
                    {f.supporting_run_ids[0] ? (
                      <button type="button" className="text-sky-400 hover:underline" onClick={() => openRun(f.supporting_run_ids[0])}>
                        {t.quantLab.resultsOpen}
                      </button>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && data && section === "prediction" && (
        <div className="grid gap-2 sm:grid-cols-2">
          <MetricCard label={t.quantLab.monitorResolved} value={data.prediction_health.resolved_count} />
          <MetricCard label={t.quantLab.monitorUnresolved} value={data.prediction_health.unresolved_count} />
          <MetricCard label={t.quantLab.monitorStale} value={data.prediction_health.stale_count} />
          <MetricCard label={t.quantLab.monitorForecastError} value={data.prediction_health.mean_forecast_error_pct ?? "—"} />
          <p className="text-xs text-zinc-500 sm:col-span-2">
            {t.quantLab.monitorCalibrationReady}: {data.prediction_health.calibration_ready ? t.common.yes : t.common.no}
          </p>
        </div>
      )}

      {!loading && section === "data" && (
        <div className="space-y-3">
          {data && (
            <ul className="list-inside list-disc text-xs text-zinc-400">
              {data.data_health.integrity_blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          )}
          <DataQualityTab />
        </div>
      )}

      {!loading && data && section === "jobs" && (
        <ul className="space-y-2 text-xs">
          {data.research_jobs.map((j) => (
            <li key={j.job_id} className="rounded border border-zinc-800 p-2">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium text-zinc-200">{j.job_name}</span>
                <span className="text-zinc-500">{j.status}</span>
              </div>
              <p className="text-zinc-500">
                {j.duration_seconds != null ? `${j.duration_seconds}s` : "—"}
                {j.run_id ? ` · run ${j.run_id}` : ""}
              </p>
              {j.error_message && <p className="text-amber-300">{j.error_message}</p>}
              <button
                type="button"
                className="mt-1 text-sky-400 hover:underline disabled:opacity-40"
                disabled={j.retry_blocked || busy === j.job_id}
                onClick={() => void onRetryJob(j.job_id)}
              >
                {t.quantLab.monitorRetryJob}
              </button>
            </li>
          ))}
        </ul>
      )}

      {!loading && data && section === "config" && (
        <div className="space-y-2 rounded-lg border border-zinc-800 p-3">
          <p className="text-xs text-zinc-300">
            strategy {data.model_configuration.strategy_version} · factor {data.model_configuration.factor_model_version}
          </p>
          <p className="text-xs text-zinc-500">
            regime: {data.model_configuration.current_regime ?? "—"} · dynamic={String(data.model_configuration.dynamic_weights_enabled)}
          </p>
          <ApplyChangesNotice />
          <p className="text-xs text-zinc-500">{t.quantLab.monitorReadOnlyConfig}</p>
        </div>
      )}

      {!loading && section === "audit" && (
        <ul className="space-y-1 text-xs text-zinc-400">
          {auditEvents.map((e) => (
            <li key={String(e.id)}>
              {String(e.event_type)} {e.symbol ? `· ${String(e.symbol)}` : ""} · {String(e.created_at ?? "")}
            </li>
          ))}
        </ul>
      )}

      {!loading && review && section === "evidence-review" && (
        <ul className="space-y-2">
          {review.findings.map((f) => (
            <li key={f.finding_id} className="rounded border border-zinc-800 p-3 text-xs">
              <div className="flex flex-wrap gap-2">
                <span className="font-medium text-zinc-200">{f.title}</span>
                <span className="text-zinc-500">{f.evidence_impact}</span>
              </div>
              {f.gate && (
                <p className="mt-1 text-zinc-500">
                  gate: {f.gate.passed_checks?.length ?? 0} passed · {f.gate.failed_checks?.length ?? 0} failed
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" className="text-sky-400" disabled={busy === f.finding_id} onClick={() => void onReviewAction(f.finding_id, "leave_informational")}>
                  {t.quantLab.monitorLeaveInformational}
                </button>
                <button type="button" className="text-sky-400" disabled={busy === f.finding_id} onClick={() => void onReviewAction(f.finding_id, "create_change_proposal")}>
                  {t.quantLab.monitorCreateProposal}
                </button>
                <button type="button" className="text-zinc-400" disabled={busy === f.finding_id} onClick={() => void onReviewAction(f.finding_id, "reject")}>
                  {t.quantLab.monitorReject}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="text-lg font-semibold tabular-nums text-zinc-100">{value}</p>
    </div>
  );
}
