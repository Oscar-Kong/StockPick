"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

const LABEL_STYLE: Record<string, string> = {
  strong_buy: "signal-buy border-emerald-500/40",
  buy: "signal-buy border-green-500/30",
  watch: "signal-hold border-amber-500/30",
  hold: "border-zinc-600 text-zinc-300",
  avoid: "signal-sell border-red-500/30",
  high_risk_no_decision: "signal-sell border-red-500/40",
};

interface RecommendationBadgeProps {
  recommendation: string;
  className?: string;
}

export function RecommendationBadge({ recommendation, className }: RecommendationBadgeProps) {
  const { t } = useTranslation();
  const recKey = recommendation as keyof typeof t.quant.recommendations;
  const label = t.quant.recommendations[recKey] ?? recommendation.replace(/_/g, " ");
  const style = LABEL_STYLE[recommendation] ?? LABEL_STYLE.watch;

  return (
    <span
      className={clsx(
        "chip px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide",
        style,
        className
      )}
    >
      {label}
    </span>
  );
}
