"use client";

import {
  displayAlgorithmName,
  extractCaveats,
  extractComparisonTable,
  formatMetric,
  pickBestRecallRow,
  scanEvalRunContext,
  type ComparisonRow,
} from "@/lib/scanEvaluationDisplay";
import type { ResearchRunDetailResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";

interface ScanEvaluationResultPanelProps {
  detail: ResearchRunDetailResponse;
  /** compact = cards only (Experiment Studio result step) */
  variant?: "full" | "compact";
}

function MetricCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-xs">
      <span className="text-zinc-500">{label}</span>
      <span className="tabular-nums text-zinc-100">{value}</span>
    </div>
  );
}

function AlgorithmCard({
  row,
  isBest,
  hitRateLabel,
  rankIcLabel,
  bestRecallLabel,
}: {
  row: ComparisonRow;
  isBest: boolean;
  hitRateLabel: string;
  rankIcLabel: string;
  bestRecallLabel: string;
}) {
  const version = String(row.algorithm_version ?? "—");
  return (
    <article
      className={`rounded-lg border p-3 ${
        isBest ? "border-emerald-800/60 bg-emerald-950/20" : "border-zinc-800 bg-zinc-950/40"
      }`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium text-zinc-100">{displayAlgorithmName(version)}</h4>
        {isBest && (
          <span className="shrink-0 rounded-full border border-emerald-800/50 px-2 py-0.5 text-[10px] uppercase tracking-wide text-emerald-300">
            {bestRecallLabel}
          </span>
        )}
      </div>
      <div className="space-y-1.5">
        <MetricCell label="Recall@10" value={formatMetric(row.recall_at_10, "percent")} />
        <MetricCell label="Recall@20" value={formatMetric(row.recall_at_20, "percent")} />
        <MetricCell label="Recall@50" value={formatMetric(row.recall_at_50, "percent")} />
        {row.mean_hit_rate_20 != null && (
          <MetricCell label={hitRateLabel} value={formatMetric(row.mean_hit_rate_20, "percent")} />
        )}
        {row.mean_rank_ic_20 != null && (
          <MetricCell label={rankIcLabel} value={formatMetric(row.mean_rank_ic_20, "decimal")} />
        )}
      </div>
    </article>
  );
}

export function ScanEvaluationResultPanel({ detail, variant = "full" }: ScanEvaluationResultPanelProps) {
  const { t } = useTranslation();
  const table = extractComparisonTable(detail.detail);
  const caveats = extractCaveats(detail.detail);
  const best = pickBestRecallRow(table);
  const bestVersion = best ? String(best.algorithm_version) : null;
  const ctx = scanEvalRunContext(detail);
  const limitationCaveats = caveats.filter((c) => !c.toLowerCase().includes("do not automatically modify"));

  if (!table.length && variant === "compact") {
    return null;
  }

  return (
    <section className="space-y-3" aria-label={t.quantLab.scanEvalComparisonTitle}>
      {variant === "full" && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full border border-zinc-700 px-2 py-0.5 uppercase tracking-wide text-zinc-400">
            {ctx.bucket}
          </span>
          <span className="tabular-nums text-zinc-500">
            {ctx.startDate} → {ctx.endDate}
          </span>
          {ctx.versions.length > 0 && (
            <span className="text-zinc-500">{ctx.versions.map(displayAlgorithmName).join(" · ")}</span>
          )}
        </div>
      )}

      <p className="text-xs text-zinc-500">{t.quantLab.scanEvalProductionNotice}</p>

      {table.length > 0 ? (
        <>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            {t.quantLab.scanEvalComparisonTitle}
          </h4>
          <div className={`grid gap-2 ${table.length > 1 ? "sm:grid-cols-2" : ""}`}>
            {table.map((row) => (
              <AlgorithmCard
                key={String(row.algorithm_version)}
                row={row}
                isBest={bestVersion != null && String(row.algorithm_version) === bestVersion}
                hitRateLabel={t.quantLab.scanEvalColHitRate}
                rankIcLabel={t.quantLab.scanEvalColRankIc}
                bestRecallLabel={t.quantLab.scanEvalBestRecall}
              />
            ))}
          </div>

          {variant === "full" && (
            <details className="rounded-lg border border-zinc-800 text-xs">
              <summary className="cursor-pointer px-3 py-2 text-zinc-400 hover:text-zinc-200">
                {t.quantLab.scanEvalAllMetrics}
              </summary>
              <div className="overflow-x-auto border-t border-zinc-800">
                <table className="min-w-full">
                  <thead className="bg-zinc-900/60 text-zinc-500">
                    <tr>
                      <th className="px-2 py-1.5 text-left">{t.quantLab.scanEvalColAlgorithm}</th>
                      <th className="px-2 py-1.5 text-left">Recall@10</th>
                      <th className="px-2 py-1.5 text-left">Recall@20</th>
                      <th className="px-2 py-1.5 text-left">Recall@50</th>
                      <th className="px-2 py-1.5 text-left">{t.quantLab.scanEvalColHitRate}</th>
                      <th className="px-2 py-1.5 text-left">{t.quantLab.scanEvalColAvgReturn}</th>
                      <th className="px-2 py-1.5 text-left">{t.quantLab.scanEvalColRankIc}</th>
                      <th className="px-2 py-1.5 text-left">{t.quantLab.scanEvalColTurnover}</th>
                      <th className="px-2 py-1.5 text-left">{t.quantLab.scanEvalColRebalanceDates}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {table.map((row) => (
                      <tr key={String(row.algorithm_version)} className="border-t border-zinc-800/80">
                        <td className="px-2 py-1.5 text-zinc-200">
                          {displayAlgorithmName(String(row.algorithm_version))}
                        </td>
                        <td className="px-2 py-1.5 tabular-nums">{formatMetric(row.recall_at_10, "percent")}</td>
                        <td className="px-2 py-1.5 tabular-nums">{formatMetric(row.recall_at_20, "percent")}</td>
                        <td className="px-2 py-1.5 tabular-nums">{formatMetric(row.recall_at_50, "percent")}</td>
                        <td className="px-2 py-1.5 tabular-nums">{formatMetric(row.mean_hit_rate_20, "percent")}</td>
                        <td className="px-2 py-1.5 tabular-nums">
                          {formatMetric(row.mean_avg_forward_return_20, "decimal")}
                        </td>
                        <td className="px-2 py-1.5 tabular-nums">{formatMetric(row.mean_rank_ic_20, "decimal")}</td>
                        <td className="px-2 py-1.5 tabular-nums">{formatMetric(row.mean_turnover_20, "decimal")}</td>
                        <td className="px-2 py-1.5 tabular-nums">{formatMetric(row.rebalance_count, "raw")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </>
      ) : (
        <p className="text-xs text-zinc-500">{t.quantLab.scanEvalNoComparison}</p>
      )}

      {variant === "full" && limitationCaveats.length > 0 && (
        <details className="text-xs text-zinc-500">
          <summary className="cursor-pointer text-zinc-400 hover:text-zinc-300">{t.quantLab.scanEvalLimitations}</summary>
          <ul className="mt-2 list-inside list-disc space-y-1 pl-1">
            {limitationCaveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
