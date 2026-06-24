"use client";

import type { ResearchRunDetailResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { ResultChart } from "./ResultChart";

type ComparisonRow = Record<string, string | number | null | undefined>;

function extractComparisonTable(detail: ResearchRunDetailResponse["detail"]): ComparisonRow[] {
  const ql = (detail?.quant_lab ?? {}) as Record<string, unknown>;
  if (Array.isArray(ql.comparison_table)) return ql.comparison_table as ComparisonRow[];
  const nested = detail?.comparison as Record<string, unknown> | undefined;
  if (nested && Array.isArray(nested.metrics_table)) return nested.metrics_table as ComparisonRow[];
  return [];
}

function extractCaveats(detail: ResearchRunDetailResponse["detail"]): string[] {
  const raw = detail?.caveats;
  if (Array.isArray(raw)) return raw.map(String);
  return [];
}

interface ScanEvaluationResultPanelProps {
  detail: ResearchRunDetailResponse;
  compact?: boolean;
}

export function ScanEvaluationResultPanel({ detail, compact = false }: ScanEvaluationResultPanelProps) {
  const { t } = useTranslation();
  const table = extractComparisonTable(detail.detail);
  const caveats = extractCaveats(detail.detail);
  const productionNotice =
    caveats.find((c) => c.includes("do not automatically modify")) ?? t.quantLab.scanEvalProductionNotice;

  const columns = [
    "algorithm_version",
    "recall_at_10",
    "recall_at_20",
    "recall_at_50",
    "mean_hit_rate_20",
    "mean_avg_forward_return_20",
    "mean_rank_ic_20",
    "mean_turnover_20",
    "rebalance_count",
  ] as const;

  const colLabels: Record<string, string> = {
    algorithm_version: t.quantLab.scanEvalColAlgorithm,
    recall_at_10: "Recall@10",
    recall_at_20: "Recall@20",
    recall_at_50: "Recall@50",
    mean_hit_rate_20: t.quantLab.scanEvalColHitRate,
    mean_avg_forward_return_20: t.quantLab.scanEvalColAvgReturn,
    mean_rank_ic_20: t.quantLab.scanEvalColRankIc,
    mean_turnover_20: t.quantLab.scanEvalColTurnover,
    rebalance_count: t.quantLab.scanEvalColRebalanceDates,
  };

  return (
    <div className="space-y-3">
      <p className="rounded border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-200/90">
        {productionNotice}
      </p>

      {table.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="min-w-full text-xs">
            <thead className="bg-zinc-900/80 text-zinc-400">
              <tr>
                {columns.map((col) => (
                  <th key={col} className="px-2 py-2 text-left">
                    {colLabels[col] ?? col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.map((row) => (
                <tr key={String(row.algorithm_version)} className="border-t border-zinc-800">
                  {columns.map((col) => (
                    <td key={col} className="px-2 py-2 tabular-nums text-zinc-200">
                      {row[col] != null ? String(row[col]) : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!compact && detail.charts.length > 0 && (
        <div className="grid gap-3 lg:grid-cols-2">
          {detail.charts.map((c) => (
            <ResultChart key={c.chart_id} chart={c} />
          ))}
        </div>
      )}

      {caveats.length > 0 && (
        <ul className="list-inside list-disc text-xs text-zinc-500">
          {caveats
            .filter((c) => !c.includes("do not automatically modify"))
            .map((c) => (
              <li key={c}>{c}</li>
            ))}
        </ul>
      )}

      {detail.detail?.artifact_paths && (
        <p className="text-xs text-zinc-600">
          {t.quantLab.scanEvalArtifacts}:{" "}
          <span className="tabular-nums text-zinc-400">
            {String((detail.detail.artifact_paths as Record<string, string>).root ?? "—")}
          </span>
        </p>
      )}
    </div>
  );
}
