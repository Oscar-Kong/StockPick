"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

const LABEL_STYLE: Record<string, string> = {
  strong_buy: "border-emerald-500/40 text-emerald-300",
  buy: "border-green-500/30 text-green-300",
  watch: "border-amber-500/30 text-amber-200",
  hold: "border-zinc-600 text-zinc-300",
  avoid: "border-red-500/30 text-red-300",
  high_risk_no_decision: "border-red-500/40 text-red-200",
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
