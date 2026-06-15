"use client";

import { useTranslation } from "@/lib/i18n";
import type { PositionSizingV2 } from "@/lib/types";
import { StatTile } from "@/components/ui/StatTile";

interface PositionSizingBlockProps {
  sizing: PositionSizingV2 | null;
  loading?: boolean;
  error?: string | null;
}

export function PositionSizingBlock({ sizing, loading, error }: PositionSizingBlockProps) {
  const { t } = useTranslation();

  if (loading) {
    return <p className="text-xs text-zinc-500">{t.quant.loadingSizing}</p>;
  }
  if (error) {
    return <p className="text-xs text-amber-400/90">{error}</p>;
  }
  if (!sizing) {
    return <p className="text-xs text-zinc-500">{t.quant.sizingDisabled}</p>;
  }

  return (
    <div className="space-y-3 rounded-xl border border-[#00c805]/25 bg-[#00c805]/5 p-4">
      <dl className="grid gap-3 sm:grid-cols-2">
        <StatTile
          label={t.quant.recommended}
          value={
            <span className="tabular-nums text-[#7dff8e]">
              {sizing.recommended_weight_pct.toFixed(1)}%
            </span>
          }
        />
        <StatTile
          label={t.quant.maxSleeve}
          value={
            <span className="tabular-nums">{sizing.max_weight_pct.toFixed(1)}%</span>
          }
        />
        <StatTile
          label={t.quant.stopLoss}
          value={<span className="tabular-nums">{sizing.stop_loss_pct.toFixed(1)}%</span>}
        />
        <StatTile
          label={t.quant.conviction}
          value={<span className="tabular-nums">{sizing.conviction.toFixed(0)}%</span>}
        />
      </dl>
      <p className="text-xs leading-relaxed text-zinc-500">{sizing.rationale}</p>
    </div>
  );
}
