"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";
import type { StockResult } from "@/lib/types";

function pillarColor(value: number): string {
  if (value >= 70) return "text-emerald-300";
  if (value >= 45) return "text-amber-200";
  return "text-red-300/90";
}

function readPillar(stock: StockResult, key: "alpha_score" | "confidence_score" | "tradability_score"): number | null {
  const top = stock[key];
  if (typeof top === "number" && Number.isFinite(top)) return top;
  const m = stock.metrics ?? {};
  const nested = m[key];
  if (typeof nested === "number" && Number.isFinite(nested)) return nested;
  return null;
}

interface ScanScoreBreakdownProps {
  stock: StockResult;
  compact?: boolean;
  className?: string;
}

/** Alpha / confidence / tradability — separate from composite ranking score. */
export function ScanScoreBreakdown({ stock, compact, className }: ScanScoreBreakdownProps) {
  const { t } = useTranslation();
  const alpha = readPillar(stock, "alpha_score");
  const confidence = readPillar(stock, "confidence_score");
  const tradability = readPillar(stock, "tradability_score");
  const ranking =
    typeof stock.ranking_score === "number"
      ? stock.ranking_score
      : typeof stock.metrics?.ranking_score === "number"
        ? (stock.metrics.ranking_score as number)
        : stock.score;

  if (alpha == null && confidence == null && tradability == null) {
    return (
      <span className={clsx("text-xs font-semibold tabular-nums text-zinc-200", className)}>
        {ranking.toFixed(0)}
      </span>
    );
  }

  const items = [
    { key: "alpha", label: t.scan.pillarAlpha, value: alpha },
    { key: "confidence", label: t.scan.pillarConfidence, value: confidence },
    { key: "trade", label: t.scan.pillarTradability, value: tradability },
  ].filter((item) => item.value != null);

  return (
    <div className={clsx("scan-score-breakdown", compact && "scan-score-breakdown--compact", className)}>
      <div className="scan-score-breakdown__rank" title={t.scan.rankingScore}>
        <span className="text-[10px] uppercase tracking-wide text-zinc-500">{t.scan.rankingScore}</span>
        <span className="text-sm font-semibold tabular-nums text-zinc-100">{ranking.toFixed(0)}</span>
      </div>
      <div className="scan-score-breakdown__pillars">
        {items.map((item) => (
          <div key={item.key} className="scan-score-breakdown__pillar" title={item.label}>
            <span className="scan-score-breakdown__pillar-label">{item.label}</span>
            <span className={clsx("scan-score-breakdown__pillar-value tabular-nums", pillarColor(item.value!))}>
              {item.value!.toFixed(0)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
