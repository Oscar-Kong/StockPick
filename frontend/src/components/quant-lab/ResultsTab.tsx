"use client";

import {
  createResearchRunFollowUpIdea,
  duplicateResearchRunExperiment,
  exportResearchRun,
  getResearchRunDetail,
  patchResearchRunArchive,
  patchResearchRunNotes,
} from "@/lib/api/research/runs";
import { parseApiError } from "@/lib/apiError";
import type { Bucket, ResearchRunListItem } from "@/lib/types";
import { buildQuantLabHref } from "@/lib/quantLabNavigation";
import { useTranslation } from "@/lib/i18n";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  useResearchRunCompare,
  useResearchRunDetail,
  useResearchRunList,
} from "@/hooks/useResearchRuns";
import { ResultChart } from "./ResultChart";
import { ScanEvaluationResultPanel } from "./ScanEvaluationResultPanel";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";

interface ResultsTabProps {
  sleeve: Bucket;
  onSleeveChange?: (sleeve: Bucket) => void;
}

const PAGE_SIZE = 20;

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds}s`;
  return `${Math.round(seconds / 60)}m`;
}

function MetricTip({ explanation }: { explanation: { label: string; measures: string; preferred_direction: string; why_it_matters: string; limitations: string } }) {
  return (
    <span className="group relative inline-flex cursor-help text-zinc-400 underline decoration-dotted">
      {explanation.label}
      <span className="pointer-events-none absolute bottom-full left-0 z-20 mb-1 hidden w-64 rounded border border-zinc-700 bg-zinc-900 p-2 text-left text-[11px] font-normal normal-case text-zinc-300 shadow-lg group-hover:block">
        <strong className="block text-zinc-100">{explanation.measures}</strong>
        <span className="mt-1 block">Preferred: {explanation.preferred_direction}</span>
        <span className="mt-1 block">{explanation.why_it_matters}</span>
        <span className="mt-1 block text-zinc-500">{explanation.limitations}</span>
      </span>
    </span>
  );
}

export function ResultsTab({ sleeve }: ResultsTabProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const runId = searchParams.get("run_id");
  const compareIds = searchParams.get("compare");

  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [runType, setRunType] = useState("");
  const [verdict, setVerdict] = useState("");
  const [impact, setImpact] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const loadFailed = t.quantLab.loadFailed;
  const indexEnabled = !runId && !compareIds;

  const {
    runs,
    total,
    loading: indexLoading,
    error: indexError,
    reload: loadIndex,
    setError: setIndexError,
  } = useResearchRunList(
    {
      sleeve,
      search,
      run_type: runType,
      verdict,
      evidence_impact: impact,
      status: statusFilter,
      offset,
      limit: PAGE_SIZE,
    },
    { enabled: indexEnabled, loadFailed },
  );

  const {
    detail,
    loading: detailLoading,
    error: detailError,
    setDetail,
  } = useResearchRunDetail(runId, loadFailed);

  const {
    compare,
    loading: compareLoading,
    error: compareError,
  } = useResearchRunCompare(compareIds, loadFailed);

  const loading = indexLoading || detailLoading || compareLoading;
  const error = indexError ?? detailError ?? compareError;

  const setError = (msg: string | null) => {
    setIndexError(msg);
  };

  useEffect(() => {
    if (detail) setNotesDraft(detail.summary.research_notes || "");
  }, [detail]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  const openRun = (id: string) => {
    router.push(buildQuantLabHref("results", { extra: { run_id: id } }));
  };

  const backToIndex = () => {
    router.push(buildQuantLabHref("results"));
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 4) return prev;
      return [...prev, id];
    });
  };

  const startCompare = () => {
    if (selected.length < 2) return;
    router.push(buildQuantLabHref("results", { extra: { compare: selected.join(",") } }));
  };

  const runAction = async (id: string, fn: () => Promise<unknown>) => {
    setBusy(id);
    try {
      await fn();
      await loadIndex();
    } catch (e) {
      setError(parseApiError(e, t.quantLab.runFailed));
    } finally {
      setBusy(null);
    }
  };

  if (compareIds && compare) {
    return (
      <div className="space-y-4 text-sm">
        <button type="button" className="text-sky-400 hover:underline" onClick={backToIndex}>
          {t.quantLab.resultsBack}
        </button>
        <h3 className="text-base font-semibold text-zinc-100">{t.quantLab.resultsCompareTitle}</h3>
        <p className={compare.comparable ? "text-emerald-300" : "text-amber-300"}>{compare.conclusion}</p>
        <ul className="space-y-1 text-xs text-zinc-400">
          {compare.compatibility_checks.map((c) => (
            <li key={c.key}>
              {c.label}: {c.status} — {c.detail}
            </li>
          ))}
        </ul>
        <div className="grid gap-3 lg:grid-cols-2">
          {compare.charts.map((c) => (
            <ResultChart key={c.chart_id} chart={c} />
          ))}
        </div>
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="min-w-full text-xs">
            <thead className="bg-zinc-900/80 text-zinc-400">
              <tr>
                <th className="px-2 py-2 text-left">{t.quantLab.resultsMetric}</th>
                {compare.runs.map((r) => (
                  <th key={r.run_id} className="px-2 py-2 text-left">
                    {r.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {compare.metric_diffs.map((row) => (
                <tr key={row.label} className="border-t border-zinc-800">
                  <td className="px-2 py-2 text-zinc-300">{row.label}</td>
                  {compare.runs.map((r) => (
                    <td key={r.run_id} className="px-2 py-2 tabular-nums text-zinc-200">
                      {String(row.values[r.run_id] ?? "—")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (runId && detail) {
    const interp = detail.interpretation;
    const isScanEvaluation = detail.summary.run_type === "scan_evaluation";
    return (
      <div className="space-y-4 text-sm">
        <button type="button" className="text-sky-400 hover:underline" onClick={backToIndex}>
          {t.quantLab.resultsBack}
        </button>

        {isScanEvaluation && <ScanEvaluationResultPanel detail={detail} variant="full" />}

        <header className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-emerald-800/60 bg-emerald-950/40 px-2 py-0.5 text-xs uppercase text-emerald-200">
              {interp.verdict.replace(/_/g, " ")}
            </span>
            <span className="rounded-full border border-zinc-700 px-2 py-0.5 text-xs text-zinc-300">
              {interp.evidence_impact}
            </span>
            <span className="text-xs text-zinc-500">
              {t.quantLab.resultsReliability}: {interp.reliability.score}
            </span>
          </div>
          <p className="text-zinc-100">{interp.conclusion}</p>
          {interp.prose && <p className="text-zinc-400">{interp.prose}</p>}
          <ul className="list-inside list-disc text-xs text-zinc-400">
            {interp.supporting_observations.map((o) => (
              <li key={o}>{o}</li>
            ))}
          </ul>
          <p className="text-xs text-amber-200/90">
            {t.quantLab.resultsLimitation}: {interp.main_limitation}
          </p>
          <p className="text-xs text-sky-200/90">
            {t.quantLab.resultsNextAction}: {interp.suggested_next_action}
          </p>
        </header>

        {!isScanEvaluation && (
          <div className="grid gap-3 lg:grid-cols-2">
            {detail.charts.map((c) => (
              <ResultChart key={c.chart_id} chart={c} />
            ))}
          </div>
        )}

        {detail.metric_explanations.length > 0 && (
          <div className="flex flex-wrap gap-2 text-xs">
            {detail.metric_explanations.map((m) => (
              <MetricTip key={m.metric_key} explanation={m} />
            ))}
          </div>
        )}

        <div className="rounded-lg border border-zinc-800 p-3">
          <h4 className="text-xs font-semibold uppercase text-zinc-500">{t.quantLab.resultsPrimaryMetrics}</h4>
          <ul className="mt-2 space-y-1 text-zinc-200">
            {detail.summary.primary_metrics.map((m) => (
              <li key={m.label}>
                {m.label}: <span className="tabular-nums">{String(m.value)}</span>
              </li>
            ))}
          </ul>
        </div>

        {detail.evidence_memory.length > 0 && (
          <div className="rounded-lg border border-zinc-800 p-3 space-y-2">
            <h4 className="text-xs font-semibold uppercase text-zinc-500">{t.quantLab.resultsEvidenceMemory}</h4>
            {detail.evidence_memory.map((ev) => (
              <div key={String(ev.id)} className="text-xs text-zinc-300">
                <strong>{String(ev.symbol ?? "—")}</strong>: {String(ev.deterministic_finding ?? "")}
                <span className="ml-2 text-zinc-500">({String(ev.confirmation_status ?? "pending")})</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded border border-zinc-700 px-2 py-1 text-xs hover:border-zinc-500"
            disabled={busy === runId}
            onClick={() =>
              runAction(runId, async () => {
                await duplicateResearchRunExperiment(runId);
              })
            }
          >
            {t.quantLab.resultsDuplicateExperiment}
          </button>
          <button
            type="button"
            className="rounded border border-zinc-700 px-2 py-1 text-xs hover:border-zinc-500"
            disabled={busy === runId}
            onClick={() =>
              runAction(runId, async () => {
                await createResearchRunFollowUpIdea(runId);
              })
            }
          >
            {t.quantLab.resultsFollowUpIdea}
          </button>
          <button
            type="button"
            className="rounded border border-zinc-700 px-2 py-1 text-xs hover:border-zinc-500"
            onClick={async () => {
              const data = await exportResearchRun(runId, "json");
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `${runId}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            {t.quantLab.resultsExportJson}
          </button>
        </div>

        <label className="block space-y-1">
          <span className="text-xs uppercase text-zinc-500">{t.quantLab.resultsNotes}</span>
          <textarea
            className="w-full rounded border border-zinc-800 bg-zinc-950 p-2 text-xs text-zinc-200"
            rows={3}
            value={notesDraft}
            onChange={(e) => setNotesDraft(e.target.value)}
          />
          <button
            type="button"
            className="rounded border border-zinc-700 px-2 py-1 text-xs"
            onClick={() => patchResearchRunNotes(runId, notesDraft).then(() => getResearchRunDetail(runId).then(setDetail))}
          >
            {t.quantLab.resultsSaveNotes}
          </button>
        </label>
      </div>
    );
  }

  return (
    <div className="space-y-3 text-sm">
      <p className="text-zinc-400">{t.quantLab.resultsIndexHint}</p>
      <div className="flex flex-wrap items-end gap-2">
        <input
          className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs"
          placeholder={t.quantLab.resultsSearch}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
        <select className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs" value={runType} onChange={(e) => setRunType(e.target.value)}>
          <option value="">{t.quantLab.resultsAllTypes}</option>
          <option value="walk_forward">walk_forward</option>
          <option value="factor_ic_panel">factor_ic_panel</option>
          <option value="pairs">pairs</option>
          <option value="prediction_outcomes">prediction_outcomes</option>
        </select>
        <select className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs" value={verdict} onChange={(e) => setVerdict(e.target.value)}>
          <option value="">{t.quantLab.resultsAllVerdicts}</option>
          <option value="supports_hypothesis">supports</option>
          <option value="rejects_hypothesis">rejects</option>
          <option value="inconclusive">inconclusive</option>
          <option value="insufficient_data">insufficient_data</option>
          <option value="invalid">invalid</option>
        </select>
        <select className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs" value={impact} onChange={(e) => setImpact(e.target.value)}>
          <option value="">{t.quantLab.resultsAllImpact}</option>
          <option value="informational">informational</option>
          <option value="supporting">supporting</option>
          <option value="major_positive">major_positive</option>
          <option value="major_negative">major_negative</option>
        </select>
        <select className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setOffset(0); }}>
          <option value="">{t.quantLab.resultsAllStatuses}</option>
          <option value="completed">completed</option>
          <option value="running">running</option>
          <option value="failed">failed</option>
          <option value="pending">pending</option>
        </select>
        <button
          type="button"
          className="rounded border border-sky-800/60 px-2 py-1 text-xs text-sky-300 disabled:opacity-40"
          disabled={selected.length < 2}
          onClick={startCompare}
        >
          {t.quantLab.resultsCompareSelected} ({selected.length})
        </button>
      </div>

      {error && <ErrorState message={error} onRetry={() => void loadIndex()} />}
      {loading && <LoadingSkeleton lines={6} />}

      {!loading && !error && (
        <>
          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="min-w-full text-xs">
              <thead className="bg-zinc-900/80 text-zinc-400">
                <tr>
                  <th className="px-2 py-2" />
                  <th className="px-2 py-2 text-left">{t.quantLab.resultsColName}</th>
                  <th className="px-2 py-2 text-left">{t.quantLab.resultsColType}</th>
                  <th className="px-2 py-2 text-left">{t.quantLab.resultsColSleeve}</th>
                  <th className="px-2 py-2 text-left">{t.quantLab.resultsColVerdict}</th>
                  <th className="px-2 py-2 text-left">{t.quantLab.resultsColImpact}</th>
                  <th className="px-2 py-2 text-left">{t.quantLab.resultsColReliability}</th>
                  <th className="px-2 py-2 text-left">{t.quantLab.resultsColSample}</th>
                  <th className="px-2 py-2 text-left">{t.quantLab.resultsColDuration}</th>
                  <th className="px-2 py-2 text-left">{t.quantLab.resultsColActions}</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className="border-t border-zinc-800 hover:bg-zinc-900/40">
                    <td className="px-2 py-2">
                      <input type="checkbox" checked={selected.includes(r.run_id)} onChange={() => toggleSelect(r.run_id)} />
                    </td>
                    <td className="px-2 py-2">
                      <button type="button" className="text-left text-sky-300 hover:underline" onClick={() => openRun(r.run_id)}>
                        {r.name}
                      </button>
                    </td>
                    <td className="px-2 py-2 text-zinc-400">{r.run_type}</td>
                    <td className="px-2 py-2 text-zinc-400">{r.sleeve ?? (r.universe[0] ?? "—")}</td>
                    <td className="px-2 py-2">{r.verdict ?? "—"}</td>
                    <td className="px-2 py-2">{r.evidence_impact}</td>
                    <td className="px-2 py-2 tabular-nums">{r.reliability_score ?? "—"}</td>
                    <td className="px-2 py-2 tabular-nums">{r.sample_size ?? "—"}</td>
                    <td className="px-2 py-2">{formatDuration(r.duration_seconds)}</td>
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap gap-1">
                        <button type="button" className="text-sky-400 hover:underline" onClick={() => openRun(r.run_id)}>
                          {t.quantLab.resultsOpen}
                        </button>
                        <button
                          type="button"
                          className="text-zinc-400 hover:underline"
                          disabled={busy === r.run_id}
                          onClick={() => runAction(r.run_id, () => patchResearchRunArchive(r.run_id, true))}
                        >
                          {t.quantLab.resultsArchive}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>
              {total} {t.quantLab.resultsTotal}
            </span>
            <div className="flex gap-2">
              <button type="button" disabled={offset === 0} className="disabled:opacity-40" onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                {t.quantLab.resultsPrev}
              </button>
              <span>
                {Math.floor(offset / PAGE_SIZE) + 1}/{totalPages}
              </span>
              <button
                type="button"
                disabled={offset + PAGE_SIZE >= total}
                className="disabled:opacity-40"
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                {t.quantLab.resultsNext}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
