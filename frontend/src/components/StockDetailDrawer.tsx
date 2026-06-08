// Drawer view with detailed metrics, charts, and backtest context for a stock.
"use client";

import { useTranslation } from "@/lib/i18n";
import type { StockDetail, StockResult } from "@/lib/types";
import { BacktestPanel } from "./BacktestPanel";
import { DataQualityBadge } from "./DataQualityBadge";
import { PriceChart } from "./PriceChart";
import { ScanPickSummaryCell } from "./ScanPickSummaryCell";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { ValuationBadges } from "./ValuationBadges";

interface StockDetailDrawerProps {
  stock: StockResult | null;
  detail: StockDetail | null;
  loading: boolean;
  onClose: () => void;
}

export function StockDetailDrawer({
  stock,
  detail,
  loading,
  onClose,
}: StockDetailDrawerProps) {
  const { t } = useTranslation();

  if (!stock) return null;

  const ohlc = detail?.ohlc ?? [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40">
      <div className="flex h-full w-full max-w-xl flex-col bg-white shadow-xl dark:bg-zinc-950">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-xl font-semibold">{stock.symbol}</h2>
            <p className="text-sm text-zinc-500">${stock.price.toFixed(2)}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-900"
          >
            {t.common.close}
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          <ValuationBadges
            warnings={detail?.valuation_warnings ?? stock.valuation_warnings}
            earningsSoon={detail?.earnings_soon ?? stock.earnings_soon}
            earningsDate={detail?.earnings_date ?? stock.earnings_date}
            daysUntil={detail?.days_until_earnings ?? stock.days_until_earnings ?? undefined}
          />
          <DataQualityBadge
            score={detail?.data_quality_score}
            flags={
              (stock.metrics?.data_quality_flags as string[] | undefined) ?? undefined
            }
          />
          <ScanPickSummaryCell stock={stock} variant="drawer" />

          {detail?.news_headlines && detail.news_headlines.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">{t.scan.recentNews}</h3>
              <ul className="list-inside list-disc text-xs text-zinc-600 dark:text-zinc-400">
                {detail.news_headlines.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h3 className="mb-2 text-sm font-semibold">{t.scan.scoreBreakdown}</h3>
            <ScoreBreakdown signals={stock.signals} />
          </div>

          {loading && (
            <p className="text-sm text-zinc-500">{t.scan.loadingChart}</p>
          )}

          {!loading && ohlc.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">{t.scan.priceChart}</h3>
              <PriceChart ohlc={ohlc} heightClassName="h-52" showLegend={false} />
            </div>
          )}

          {detail?.backtest && (
            <BacktestPanel
              symbol={stock.symbol}
              bucket={stock.bucket}
              embedded={detail.backtest}
            />
          )}

          {detail && Object.keys(detail.fundamentals).length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">{t.scan.keyFundamentals}</h3>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                {(
                  [
                    ["sector", t.scan.sector, detail.fundamentals.sector],
                    ["marketCap", t.scan.marketCap, detail.fundamentals.marketCap],
                    ["pe", t.scan.pe, detail.fundamentals.trailingPE ?? detail.fundamentals.pe_ratio],
                    ["revenueGrowth", t.scan.revenueGrowth, detail.fundamentals.revenueGrowth],
                    ["profitMargin", t.scan.profitMargin, detail.fundamentals.profitMargins],
                  ] as [string, string, unknown][]
                ).map(([key, label, value]) =>
                  value != null && value !== "" ? (
                    <div key={key} className="rounded-lg bg-zinc-50 p-2 dark:bg-zinc-900">
                      <dt className="text-xs text-zinc-500">{label}</dt>
                      <dd className="font-medium">
                        {typeof value === "number" && key !== "marketCap"
                          ? key === "revenueGrowth" || key === "profitMargin"
                            ? `${(value * 100).toFixed(1)}%`
                            : value.toFixed(2)
                          : key === "marketCap" && typeof value === "number"
                            ? `$${(value / 1e9).toFixed(1)}B`
                            : String(value)}
                      </dd>
                    </div>
                  ) : null
                )}
              </dl>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
