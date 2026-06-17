"use client";

import { correlationCellClass } from "@/lib/portfolioRiskColors";
import { useTranslation } from "@/lib/i18n";

interface CorrelationData {
  window?: number;
  sufficient?: boolean;
  as_of?: string | null;
  matrix?: Record<string, Record<string, number | null>>;
}

interface PortfolioCorrelationHeatmapProps {
  correlation: CorrelationData | Record<string, unknown>;
}

export function PortfolioCorrelationHeatmap({ correlation }: PortfolioCorrelationHeatmapProps) {
  const { t } = useTranslation();
  const data = correlation as CorrelationData;
  const matrix = data.matrix ?? {};
  const symbols = Object.keys(matrix).sort();
  if (!data.sufficient || symbols.length < 2) return null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="label-caps">{t.portfolio.correlationHeatmap}</h4>
        <p className="text-[10px] text-zinc-500">
          {t.portfolio.correlationWindow.replace("{n}", String(data.window ?? 60))}
          {data.as_of ? ` · ${data.as_of}` : ""}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-0.5 text-[10px]">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-zinc-950 px-1 py-0.5 text-left text-zinc-500" />
              {symbols.map((sym) => (
                <th key={sym} className="px-1 py-0.5 font-medium text-zinc-500">
                  {sym}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbols.map((rowSym) => (
              <tr key={rowSym}>
                <th className="sticky left-0 z-10 bg-zinc-950 px-1 py-0.5 text-left font-medium text-zinc-400">
                  {rowSym}
                </th>
                {symbols.map((colSym) => {
                  const val = matrix[rowSym]?.[colSym];
                  const isDiag = rowSym === colSym;
                  return (
                    <td
                      key={colSym}
                      title={
                        val != null
                          ? `${rowSym} × ${colSym}: ${val.toFixed(2)}`
                          : undefined
                      }
                      className={`min-w-[2.25rem] px-1 py-0.5 text-center tabular-nums ${correlationCellClass(val, isDiag)}`}
                    >
                      {val != null ? val.toFixed(2) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-2 text-[10px] text-zinc-500">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 rounded-sm bg-emerald-500/30" /> Low
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 rounded-sm bg-amber-500/30" /> Moderate
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 rounded-sm bg-orange-500/30" /> High
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 rounded-sm bg-red-500/40" /> Clustered
        </span>
      </div>
    </div>
  );
}
