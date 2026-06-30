"use client";

import type { BrokerageCsvImportResponse, CsvPreviewResponse, DailyDashboardResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { CsvImportFooter, ClosedPositionsPanel } from "@/components/dashboard/daily-decision/DailyDecisionPanels";
import { CsvImportReviewPanel } from "@/components/portfolio/CsvImportReviewPanel";
import { PortfolioLedgerPanel } from "@/components/portfolio/PortfolioLedgerPanel";
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
  csvPreview: CsvPreviewResponse | null;
  onCsvPreviewCancel: () => void;
  onCsvApproved: (result: BrokerageCsvImportResponse) => void;
  ledgerRefreshKey: number;
  onLedgerChanged: () => void;
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
  csvPreview,
  onCsvPreviewCancel,
  onCsvApproved,
  ledgerRefreshKey,
  onLedgerChanged,
}: PortfolioActivityProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      <SectionCard title={t.portfolio.activityImportTitle} subtitle={t.portfolio.activityImportSubtitle} variant="elevated">
        {csvPreview ? (
          <CsvImportReviewPanel
            preview={csvPreview}
            replace={replaceImport}
            onCancel={onCsvPreviewCancel}
            onApproved={onCsvApproved}
          />
        ) : (
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
        )}
      </SectionCard>

      <SectionCard title={t.portfolio.ledgerTitle} subtitle={t.portfolio.ledgerSubtitle} variant="elevated">
        <PortfolioLedgerPanel key={ledgerRefreshKey} onChanged={onLedgerChanged} />
      </SectionCard>

      {(data.closed_positions?.length ?? 0) > 0 && (
        <ClosedPositionsPanel closed={data.closed_positions ?? []} />
      )}
    </div>
  );
}
