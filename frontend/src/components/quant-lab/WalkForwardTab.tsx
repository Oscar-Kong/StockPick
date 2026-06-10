"use client";

import { ResearchWarning } from "@/components/ui/ResearchWarning";
import { ResearchOnlyBadge } from "@/components/ui/ResearchOnlyBadge";
import { TooltipLabel } from "@/components/ui/TooltipLabel";
import { ApplyChangesNotice } from "@/components/product/ApplyChangesNotice";
import { getWalkForwardLatest, getWalkForwardRun, runWalkForwardResearch } from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import {
  defaultWalkForwardDates,
  formatWalkForwardHorizonStats,
  validateWalkForwardDates,
} from "@/lib/quantLabFormatters";
import { normalizeWalkForwardResearchResponse } from "@/lib/quantLabNormalizers";
import { saveWalkForwardLastRun, validateWalkForwardHorizons } from "@/lib/quantLabStability";
import {
  computeWalkForwardOverfittingWarnings,
  computeWalkForwardReliability,
  translateReliabilityList,
} from "@/lib/researchReliability";
import type { Bucket, QuantLabLastRunSummary } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { useEffect, useMemo, useState } from "react";
import { BucketSelect, QuantLabEmptyState, QuantLabTabLayout } from "./QuantLabTabShell";
import { QuantLabTrustBadge } from "./QuantLabTrustBadge";
import { ResearchReliabilityCard } from "./ResearchReliabilityCard";

const HORIZON_OPTIONS = [20, 60, 90] as const;

export function WalkForwardTab() {
  const { t } = useTranslation();
  const defaults = useMemo(() => defaultWalkForwardDates(), []);
  const [sleeve, setSleeve] = useState<Bucket>("penny");
  const [startDate, setStartDate] = useState(defaults.start_date);
  const [endDate, setEndDate] = useState(defaults.end_date);
  const [horizons, setHorizons] = useState<number[]>([20, 60]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Awaited<ReturnType<typeof runWalkForwardResearch>> | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [latestSummary, setLatestSummary] = useState<QuantLabLastRunSummary | null>(null);
  const [loadingLatest, setLoadingLatest] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoadingLatest(true);
    void (async () => {
      try {
        const latest = await getWalkForwardLatest(sleeve);
        if (cancelled) return;
        setLatestSummary(latest);
        if (latest.available && latest.run_id) {
          const detail = await getWalkForwardRun(latest.run_id);
          if (cancelled || !detail.summary) return;
          setResult(normalizeWalkForwardResearchResponse(detail.summary));
        } else {
          setResult(null);
        }
      } catch {
        if (!cancelled) setLatestSummary(null);
      } finally {
        if (!cancelled) setLoadingLatest(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sleeve]);

  const toggleHorizon = (h: number) => {
    setHorizons((prev) =>
      prev.includes(h) ? prev.filter((x) => x !== h) : [...prev, h].sort((a, b) => a - b)
    );
  };

  const run = async () => {
    setValidationError(null);
    setError(null);
    const dateErr = validateWalkForwardDates(startDate, endDate);
    if (dateErr === "invalid_date") {
      setValidationError(t.quantLab.walkForwardInvalidDate);
      return;
    }
    if (dateErr === "start_after_end") {
      setValidationError(t.quantLab.walkForwardStartAfterEnd);
      return;
    }
    const horizonErr = validateWalkForwardHorizons(horizons);
    if (horizonErr === "no_horizons") {
      setValidationError(t.quantLab.walkForwardNoHorizons);
      return;
    }

    setRunning(true);
    try {
      const res = await runWalkForwardResearch({
        sleeve,
        start_date: startDate,
        end_date: endDate,
        forward_horizons: horizons,
        max_symbols: 25,
      });
      setResult(res);
      saveWalkForwardLastRun(res);
      setLatestSummary(await getWalkForwardLatest(sleeve));
    } catch (e) {
      setResult(null);
      setError(parseApiError(e, t.quantLab.runFailed));
    } finally {
      setRunning(false);
    }
  };

  const horizonRows = result?.aggregate_horizons
    ? Object.entries(result.aggregate_horizons)
    : [];

  const reliability = useMemo(
    () =>
      computeWalkForwardReliability({
        result,
        latestStale: latestSummary?.stale,
        loading: loadingLatest || running,
      }),
    [result, latestSummary?.stale, loadingLatest, running]
  );

  const overfitting = useMemo(() => computeWalkForwardOverfittingWarnings(result), [result]);
  const overfittingLines = translateReliabilityList(overfitting.warnings, "warnings", t);

  return (
    <QuantLabTabLayout
      title={t.quantLab.tabWalkForward}
      description={
        <TooltipLabel label={t.quantLab.hintWalkForward} tooltip={t.product.walkForwardTooltip} />
      }
      reliability={<ResearchReliabilityCard score={reliability} />}
      statusBadge={
        <>
          <ResearchOnlyBadge tooltip={t.product.walkForwardTooltip} />
          {latestSummary && !loadingLatest ? (
            <QuantLabTrustBadge indicator={latestSummary.trust_indicator} />
          ) : null}
        </>
      }
      controls={
        <div className="space-y-3">
          <ResearchWarning message={t.quantLab.researchOnlyExtended} />
          {latestSummary?.available && latestSummary.generated_at && (
            <p className="text-xs text-zinc-500">
              {t.quantLab.lastWalkForwardRun}: {latestSummary.generated_at.slice(0, 10)}
              {latestSummary.sample_size != null && ` · ${latestSummary.sample_size} ${t.quantLab.periodsScored.toLowerCase()}`}
              {latestSummary.stale && latestSummary.stale_reason && (
                <span className="text-amber-300"> · {latestSummary.stale_reason}</span>
              )}
            </p>
          )}
          <div className="flex flex-wrap items-end gap-3">
            <BucketSelect
              label={t.common.bucket}
              value={sleeve}
              onChange={(v) => setSleeve(v as Bucket)}
            />
            <label className="text-xs text-zinc-500">
              {t.quantLab.startDate}
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
              />
            </label>
            <label className="text-xs text-zinc-500">
              {t.quantLab.endDate}
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
              />
            </label>
          </div>
          <fieldset className="flex flex-wrap gap-3 text-xs text-zinc-500">
            <legend className="sr-only">{t.quantLab.forwardHorizons}</legend>
            {HORIZON_OPTIONS.map((h) => (
              <label key={h} className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={horizons.includes(h)}
                  onChange={() => toggleHorizon(h)}
                />
                {h}d
              </label>
            ))}
          </fieldset>
          <button
            type="button"
            onClick={() => void run()}
            disabled={running}
            className="btn-primary px-3 py-1.5 text-sm"
          >
            {running ? t.common.running : t.quantLab.runWalkForward}
          </button>
          {validationError && <p className="text-xs text-amber-300">{validationError}</p>}
        </div>
      }
      error={error}
      onRetry={() => void run()}
    >
      {result && (
        <div className="space-y-4">
          <ApplyChangesNotice />
          {overfittingLines.length > 0 && (
            <div
              className="rounded-lg border border-amber-900/40 bg-amber-950/20 p-3"
              data-testid="walk-forward-overfitting-warnings"
            >
              <h4 className="text-xs font-semibold text-amber-200">{t.quantLab.overfittingTitle}</h4>
              <p className="mt-1 text-[10px] text-amber-200/70">
                PBO: {overfitting.pbo_available ? "yes" : "no"} —{" "}
                {translateReliabilityList([overfitting.pbo_warning], "warnings", t)[0]}
              </p>
              <ul className="mt-2 list-inside list-disc text-xs text-amber-200/90">
                {overfittingLines.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </div>
          )}
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-zinc-500">{t.quantLab.runStatus}</dt>
              <dd>{result.status || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">{t.quantLab.periodsScored}</dt>
              <dd>{result.periods_scored ?? 0}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">{t.quantLab.meanTurnover}</dt>
              <dd>
                {result.mean_turnover != null && Number.isFinite(result.mean_turnover)
                  ? result.mean_turnover.toFixed(3)
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">{t.quantLab.runId}</dt>
              <dd className="truncate font-mono text-xs">{result.run_id || "—"}</dd>
            </div>
          </dl>
          {horizonRows.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium text-zinc-400">{t.quantLab.aggregateHorizons}</h4>
              <ul className="space-y-1 text-xs text-zinc-500">
                {horizonRows.map(([horizon, stats]) => (
                  <li key={horizon}>
                    {horizon}d: {formatWalkForwardHorizonStats(stats)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.periods_scored === 0 && (
            <QuantLabEmptyState message={t.quantLab.walkForwardNoPeriods} />
          )}
        </div>
      )}
      {!result && !running && !error && !loadingLatest && (
        <QuantLabEmptyState message={t.quantLab.walkForwardNoRunYet} />
      )}
    </QuantLabTabLayout>
  );
}
