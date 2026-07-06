"use client";

import { RobinhoodSyncButton } from "@/components/portfolio/RobinhoodSyncButton";
import { LedgerSidePill, ledgerSelectClass } from "@/components/portfolio/ledger-ui";
import { useTradingHistory } from "@/components/portfolio/useTradingHistory";
import { DenseTable, DenseTableNumericCell } from "@/components/ui/DenseTable";
import {
  ALL_MONTHS,
  ALL_YEARS,
  formatTradeAmount,
  formatTradePrice,
  formatTradeQuantity,
} from "@/lib/tradingHistory";
import { fmt, useTranslation } from "@/lib/i18n";

type TradingHistoryModuleProps = {
  reloadToken?: number;
  onSync?: () => void;
  syncing?: boolean;
  syncDisabled?: boolean;
  syncMessage?: string | null;
  syncError?: string | null;
};

function sideLabel(side: string, t: ReturnType<typeof useTranslation>["t"]): string {
  const s = side.toLowerCase();
  if (s === "buy") return t.portfolio.sideBuy;
  if (s === "sell") return t.portfolio.sideSell;
  return t.portfolio.sideEvent;
}

function monthLabel(month: number, locale: string): string {
  return new Date(Date.UTC(2020, month - 1, 1)).toLocaleString(locale, { month: "short" });
}

export function TradingHistoryModule({
  reloadToken = 0,
  onSync,
  syncing = false,
  syncDisabled = false,
  syncMessage,
  syncError,
}: TradingHistoryModuleProps) {
  const { t, locale } = useTranslation();
  const { filtered, rows, loading, error, year, month, years, availableMonths, setYear, setMonth } =
    useTradingHistory(reloadToken);

  return (
    <section className="trading-history space-y-3" aria-labelledby="trading-history-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="trading-history-heading" className="text-base font-semibold text-foreground">
            {t.portfolio.tradingHistoryTitle}
          </h2>
          <p className="mt-0.5 text-xs leading-relaxed text-secondary">{t.portfolio.tradingHistorySubtitle}</p>
        </div>
        {onSync && (
          <RobinhoodSyncButton syncing={syncing} disabled={syncDisabled} onSync={onSync} />
        )}
      </div>

      {(syncError || syncMessage) && (
        <p className={`text-xs ${syncError ? "text-negative" : "text-secondary"}`}>
          {syncError ?? syncMessage}
        </p>
      )}

      <div className="trading-history__filters flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-secondary">
        <label className="flex items-center gap-1.5">
          <span className="shrink-0">{t.portfolio.tradingHistoryFilterYear}</span>
          <select
            className={ledgerSelectClass}
            value={year === ALL_YEARS ? ALL_YEARS : String(year)}
            aria-label={t.portfolio.tradingHistoryFilterYear}
            onChange={(e) => {
              const v = e.target.value;
              setYear(v === ALL_YEARS ? ALL_YEARS : Number(v));
            }}
          >
            <option value={ALL_YEARS}>{t.portfolio.tradingHistoryAllYears}</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-1.5">
          <span className="shrink-0">{t.portfolio.tradingHistoryFilterMonth}</span>
          <select
            className={ledgerSelectClass}
            value={month === ALL_MONTHS ? ALL_MONTHS : String(month)}
            aria-label={t.portfolio.tradingHistoryFilterMonth}
            onChange={(e) => {
              const v = e.target.value;
              setMonth(v === ALL_MONTHS ? ALL_MONTHS : Number(v));
            }}
          >
            <option value={ALL_MONTHS}>{t.portfolio.tradingHistoryAllMonths}</option>
            {availableMonths.map((m) => (
              <option key={m} value={m}>
                {monthLabel(m, locale)}
              </option>
            ))}
          </select>
        </label>

        <span className="tabular-nums text-tertiary">
          {fmt(t.portfolio.tradingHistoryShowing, { shown: filtered.length, total: rows.length })}
        </span>
      </div>

      {error && <div className="ledger-notice ledger-notice--error text-sm">{error}</div>}

      {loading ? (
        <p className="text-sm text-secondary">{t.common.loading}</p>
      ) : filtered.length === 0 ? (
        <p className="trading-history__empty">{t.portfolio.tradingHistoryEmpty}</p>
      ) : (
        <DenseTable caption={t.portfolio.tradingHistoryTitle} className="trading-history-table">
          <colgroup>
            <col className="trading-history-table__col-date" />
            <col className="trading-history-table__col-symbol" />
            <col className="trading-history-table__col-side" />
            <col className="trading-history-table__col-qty" />
            <col className="trading-history-table__col-price" />
            <col className="trading-history-table__col-amount" />
          </colgroup>
          <thead>
            <tr>
              <th scope="col" className="col-text">
                {t.portfolio.ledgerColDate}
              </th>
              <th scope="col" className="col-text">
                {t.portfolio.ledgerColSymbol}
              </th>
              <th scope="col" className="col-center">
                {t.portfolio.ledgerColSide}
              </th>
              <th scope="col" className="col-num">
                {t.portfolio.ledgerColQty}
              </th>
              <th scope="col" className="col-num">
                {t.portfolio.ledgerColPrice}
              </th>
              <th scope="col" className="col-num">
                {t.portfolio.ledgerColAmount}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id}>
                <td className="col-text tabular-nums text-secondary">{row.activity_date ?? "—"}</td>
                <td className="col-text font-mono font-semibold text-symbol">{row.symbol}</td>
                <td className="col-center">
                  <LedgerSidePill side={row.side} label={sideLabel(row.side, t)} />
                </td>
                <DenseTableNumericCell>{formatTradeQuantity(row.quantity)}</DenseTableNumericCell>
                <DenseTableNumericCell>{formatTradePrice(row.price)}</DenseTableNumericCell>
                <DenseTableNumericCell>{formatTradeAmount(row.amount)}</DenseTableNumericCell>
              </tr>
            ))}
          </tbody>
        </DenseTable>
      )}
    </section>
  );
}
