"use client";

import { useTranslation } from "@/lib/i18n";
import type { PositionSizingV2 } from "@/lib/types";

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
    <div className="space-y-2 rounded-lg border border-[#00c805]/25 bg-[#00c805]/5 p-2.5">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">{t.quant.recommended}</p>
          <p className="text-lg font-semibold tabular-nums text-[#7dff8e]">
            {sizing.recommended_weight_pct.toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">{t.quant.maxSleeve}</p>
          <p className="text-lg font-semibold tabular-nums text-zinc-100">
            {sizing.max_weight_pct.toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">{t.quant.stopLoss}</p>
          <p className="text-sm font-medium tabular-nums text-zinc-200">
            {sizing.stop_loss_pct.toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">{t.quant.conviction}</p>
          <p className="text-sm font-medium tabular-nums text-zinc-200">
            {sizing.conviction.toFixed(0)}%
          </p>
        </div>
      </div>
      <p className="text-[10px] leading-snug text-zinc-500">{sizing.rationale}</p>
    </div>
  );
}
