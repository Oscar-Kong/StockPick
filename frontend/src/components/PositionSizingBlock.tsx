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
    return (
      <div className="position-sizing-panel position-sizing-panel--loading" aria-busy="true">
        <p className="text-xs text-zinc-500">{t.quant.loadingSizing}</p>
        <div className="position-sizing-skeleton" aria-hidden />
      </div>
    );
  }
  if (error) {
    return <p className="text-xs text-amber-400/90">{error}</p>;
  }
  if (!sizing) {
    return <p className="text-xs text-zinc-500">{t.quant.sizingDisabled}</p>;
  }

  return (
    <div className="position-sizing-panel space-y-3">
      <dl className="grid gap-2 grid-cols-2">
        <StatTile
          label={t.quant.recommended}
          value={
            <span className="tabular-nums text-buy">
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
