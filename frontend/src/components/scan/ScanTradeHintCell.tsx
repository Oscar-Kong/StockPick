"use client";

import { RecommendationBadge } from "@/components/badges/RecommendationBadge";
import { getScanTradeHint } from "@/lib/scanTradeHint";
import { fmt, useTranslation } from "@/lib/i18n";
import type { StockResult } from "@/lib/types";
import clsx from "clsx";

interface ScanTradeHintCellProps {
  stock: StockResult;
  compact?: boolean;
  className?: string;
}

export function ScanTradeHintCell({ stock, compact, className }: ScanTradeHintCellProps) {
  const { t } = useTranslation();
  const hint = getScanTradeHint(stock);

  return (
    <div
      className={clsx("scan-trade-hint", compact && "scan-trade-hint--compact", className)}
      title={hint.reason}
    >
      <RecommendationBadge recommendation={hint.recommendation} className="scan-trade-hint__badge" />
      <div className="scan-trade-hint__bar" aria-hidden>
        <span className="scan-trade-hint__buy" style={{ width: `${hint.buyPct}%` }} />
        <span className="scan-trade-hint__wait" style={{ width: `${hint.waitPct}%` }} />
      </div>
      <p className="scan-trade-hint__pct finance-value">
        <span className="scan-trade-hint__buy-label">
          {fmt(t.scan.tradeHintBuyPct, { pct: hint.buyPct.toFixed(0) })}
        </span>
        <span className="scan-trade-hint__sep">·</span>
        <span className="scan-trade-hint__wait-label">
          {fmt(t.scan.tradeHintWaitPct, { pct: hint.waitPct.toFixed(0) })}
        </span>
      </p>
    </div>
  );
}
