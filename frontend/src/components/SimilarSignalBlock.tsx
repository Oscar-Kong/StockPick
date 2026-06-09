"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { SimilarSignalV2 } from "@/lib/types";
import { ResearchOnlyBadge } from "./ui/ResearchOnlyBadge";
import { TooltipLabel } from "./ui/TooltipLabel";

export function SimilarSignalBlock({ data }: { data: SimilarSignalV2 }) {
  const { t } = useTranslation();

  if (!data.sample_n) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 text-xs text-zinc-500">
        {t.quant.similarInsufficient}
      </div>
    );
  }
  return (
    <div className="space-y-2 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <TooltipLabel
          label={fmt(t.quant.similarBacktest, { days: data.forward_days ?? 60 })}
          tooltip={t.product.similarSignalTooltip}
          className="font-medium text-zinc-300"
        />
        <ResearchOnlyBadge tooltip={t.product.similarSignalTooltip} />
      </div>
      <div className="grid grid-cols-3 gap-2 tabular-nums">
        <div>
          <p className="text-zinc-500">{t.quant.sampleN}</p>
          <p className="text-zinc-100">{data.sample_n}</p>
        </div>
        <div>
          <p className="text-zinc-500">{t.quant.avgReturn}</p>
          <p className="text-zinc-100">{data.avg_forward_return_pct?.toFixed(1) ?? "—"}%</p>
        </div>
        <div>
          <p className="text-zinc-500">{t.quant.winRate}</p>
          <p className="text-zinc-100">
            {data.win_rate != null ? `${(data.win_rate * 100).toFixed(0)}%` : "—"}
          </p>
        </div>
      </div>
      {data.top_analogs && data.top_analogs.length > 0 && (
        <ul className="space-y-0.5 text-zinc-400">
          {data.top_analogs.slice(0, 3).map((a) => (
            <li key={`${a.symbol}-${a.date}`}>
              {a.symbol} ({a.date}): {a.forward_return_pct?.toFixed(1) ?? "—"}%
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
