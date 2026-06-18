"use client";

import type { BrokerageCsvImportResponse, DailyDashboardResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { TradeJournal } from "@/components/TradeJournal";
import { CsvImportFooter, ClosedPositionsPanel } from "@/components/dashboard/daily-decision/DailyDecisionPanels";
import { SectionCard } from "@/components/ui/AppCard";

export type PortfolioActivityProps = {
  data: DailyDashboardResponse;
  cashInput: string;
  onCashChange: (v: string) => void;
  ipoSharesInput: string;
  onIpoSharesChange: (v: string) => void;
  ipoListPriceInput: string;
  onIpoListPriceChange: (v: string) => void;
  reservedInput: string;
  onReservedChange: (v: string) => void;
  replaceImport: boolean;
  onReplaceChange: (v: boolean) => void;
  onImportClick: () => void;
  onSaveBuyingPower: () => void;
  savingCash: boolean;
  importing: boolean;
  lastImport: BrokerageCsvImportResponse | null;
};

export function PortfolioActivity({
  data,
  cashInput,
  onCashChange,
  ipoSharesInput,
  onIpoSharesChange,
  ipoListPriceInput,
  onIpoListPriceChange,
  reservedInput,
  onReservedChange,
  replaceImport,
  onReplaceChange,
  onImportClick,
  onSaveBuyingPower,
  savingCash,
  importing,
  lastImport,
}: PortfolioActivityProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      <SectionCard title={t.portfolio.activityImportTitle} subtitle={t.portfolio.activityImportSubtitle} variant="elevated">
        <CsvImportFooter
          cashInput={cashInput}
          onCashChange={onCashChange}
          ipoSharesInput={ipoSharesInput}
          onIpoSharesChange={onIpoSharesChange}
          ipoListPriceInput={ipoListPriceInput}
          onIpoListPriceChange={onIpoListPriceChange}
          reservedInput={reservedInput}
          onReservedChange={onReservedChange}
          replaceImport={replaceImport}
          onReplaceChange={onReplaceChange}
          onImportClick={onImportClick}
          onSaveBuyingPower={onSaveBuyingPower}
          savingCash={savingCash}
          importing={importing}
          lastImport={lastImport}
          csvRowsLoaded={data.csv_rows_loaded}
          ledgerRowsCount={data.ledger_rows_count}
        />
      </SectionCard>

      <SectionCard title={t.command.tradeJournal} subtitle={t.portfolio.activityJournalSubtitle} variant="elevated">
        <TradeJournal compact />
      </SectionCard>

      {(data.closed_positions?.length ?? 0) > 0 && (
        <ClosedPositionsPanel closed={data.closed_positions ?? []} />
      )}
    </div>
  );
}
