"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { RecommendationV2 } from "@/lib/types";
import clsx from "clsx";

const LABEL_STYLE: Record<string, string> = {
  strong_buy: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  buy: "bg-green-500/15 text-green-300 border-green-500/30",
  watch: "bg-amber-500/15 text-amber-200 border-amber-500/30",
  hold: "bg-zinc-500/15 text-zinc-300 border-zinc-600/40",
  avoid: "bg-red-500/15 text-red-300 border-red-500/30",
  high_risk_no_decision: "bg-red-500/20 text-red-200 border-red-500/40",
};

export function RecommendationBlock({ data }: { data: RecommendationV2 }) {
  const { t } = useTranslation();
  const recKey = data.recommendation as keyof typeof t.quant.recommendations;
  const label = t.quant.recommendations[recKey] ?? data.recommendation.replace(/_/g, " ");
  const style = LABEL_STYLE[data.recommendation] ?? LABEL_STYLE.watch;

  return (
    <div className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={clsx("rounded-md border px-2 py-0.5 text-xs font-semibold uppercase", style)}>
          {label}
        </span>
        <span className="text-sm tabular-nums text-zinc-300">
          {fmt(t.quant.confidence, { value: data.confidence.toFixed(0) })}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <p className="text-zinc-500">{t.quant.alpha}</p>
          <p className="font-semibold text-zinc-100">{data.pillars.alpha_score.toFixed(0)}</p>
        </div>
        <div>
          <p className="text-zinc-500">{t.quant.valuation}</p>
          <p className="font-semibold text-zinc-100">{data.pillars.valuation_score.toFixed(0)}</p>
        </div>
        <div>
          <p className="text-zinc-500">{t.quant.catalyst}</p>
          <p className="font-semibold text-zinc-100">{data.pillars.catalyst_score.toFixed(0)}</p>
        </div>
      </div>
      <p className="text-xs text-zinc-400">
        {fmt(t.quant.horizon, {
          days: data.time_horizon_days,
          up: data.expected_return_pct.toFixed(1),
          down: data.expected_downside_pct.toFixed(1),
        })}
      </p>
      <div className="text-xs">
        <p className="text-zinc-500">
          {fmt(t.quant.dataConfidence, {
            value: data.data_confidence.data_confidence.toFixed(0),
          })}
        </p>
        {data.data_confidence.issues.slice(0, 3).map((issue, idx) => (
          <p key={`issue-${idx}-${issue}`} className="text-amber-200/80">
            • {issue}
          </p>
        ))}
        {data.gates.map((g, idx) => (
          <p key={`gate-${idx}-${g}`} className="text-amber-300">
            {t.quant.gate} {g}
          </p>
        ))}
      </div>
      <div className="space-y-1 text-xs">
        <p>
          <span className="text-emerald-400">{t.quant.bull}</span> {data.bull_case}
        </p>
        <p>
          <span className="text-red-400">{t.quant.bear}</span> {data.bear_case}
        </p>
      </div>
    </div>
  );
}
