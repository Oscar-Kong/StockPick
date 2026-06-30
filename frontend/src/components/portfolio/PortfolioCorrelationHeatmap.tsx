"use client";

import {
  correlationStrength,
  correlationStrengthLabel,
  formatCorrelationCellAria,
} from "@/lib/correlationLabels";
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

  const labelMessages = {
    perfect: t.portfolio.correlationPerfect,
    strongPositive: t.portfolio.correlationStrongPositive,
    moderatePositive: t.portfolio.correlationModeratePositive,
    weakPositive: t.portfolio.correlationWeakPositive,
    negligible: t.portfolio.correlationNegligible,
    weakNegative: t.portfolio.correlationWeakNegative,
    moderateNegative: t.portfolio.correlationModerateNegative,
    strongNegative: t.portfolio.correlationStrongNegative,
    cellAria: t.portfolio.correlationCellAria,
  };

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
        <table className="border-separate border-spacing-0.5 text-[10px]" role="grid" aria-label={t.portfolio.correlationHeatmap}>
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-zinc-950 px-1 py-0.5 text-left text-zinc-500" scope="col" />
              {symbols.map((sym) => (
                <th key={sym} scope="col" className="px-1 py-0.5 font-medium text-zinc-500">
                  {sym}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbols.map((rowSym) => (
              <tr key={rowSym}>
                <th scope="row" className="sticky left-0 z-10 bg-zinc-950 px-1 py-0.5 text-left font-medium text-zinc-400">
                  {rowSym}
                </th>
                {symbols.map((colSym) => {
                  const val = matrix[rowSym]?.[colSym];
                  const isDiag = rowSym === colSym;
                  const strength = correlationStrength(val, isDiag);
                  const strengthText = correlationStrengthLabel(strength, labelMessages);
                  const ariaLabel = formatCorrelationCellAria(rowSym, colSym, val, isDiag, labelMessages);
                  const display =
                    val != null
                      ? `${rowSym} / ${colSym}\nCorrelation: ${val.toFixed(2)}\n${strengthText}`
                      : undefined;
                  return (
                    <td
                      key={colSym}
                      role="gridcell"
                      title={display}
                      aria-label={ariaLabel}
                      className={`min-w-[2.25rem] px-1 py-0.5 text-center tabular-nums ${correlationCellClass(val, isDiag)}`}
                    >
                      <span className="block font-medium">{val != null ? val.toFixed(2) : "—"}</span>
                      <span className="sr-only">{strengthText}</span>
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
          <span className="inline-block h-2 w-4 rounded-sm bg-emerald-500/30" aria-hidden /> Low
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 rounded-sm bg-amber-500/30" aria-hidden /> Moderate
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 rounded-sm bg-orange-500/30" aria-hidden /> High
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 rounded-sm bg-red-500/40" aria-hidden /> Clustered
        </span>
      </div>
    </div>
  );
}
