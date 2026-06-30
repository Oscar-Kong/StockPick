import Link from "next/link";
import type { BrokerageCsvImportResponse } from "@/lib/types";
import type { PennyOpportunityItem } from "@/lib/types";
import { formatCurrency } from "@/lib/dailyDecisionUtils";
import { useTranslation } from "@/lib/i18n";
import { AppCard, SectionCard } from "@/components/ui/AppCard";
import { GhostButton, PrimaryButton } from "@/components/ui/buttons";

export function EmptyPortfolioState({ onImportClick }: { onImportClick: () => void }) {
  const { t } = useTranslation();
  return (
    <AppCard variant="ghost" className="px-6 py-14 text-center md:px-10">
      <h2 className="text-xl font-semibold tracking-tight text-zinc-50">{t.home.dailyEmptyTitle}</h2>
      <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-secondary">{t.home.dailyEmptyDescription}</p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <PrimaryButton onClick={onImportClick} className="rounded-xl">
          {t.home.dailyImportCsv}
        </PrimaryButton>
      </div>
      <p className="mt-5 text-sm text-secondary">{t.home.dailyCsvWhereHint}</p>
    </AppCard>
  );
}

export type CsvImportFooterProps = {
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
  csvRowsLoaded?: number | null;
  ledgerRowsCount?: number | null;
};

function CsvImportOptions({
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
  onSaveBuyingPower,
  savingCash,
  importing,
  lastImport,
  csvRowsLoaded,
  ledgerRowsCount,
}: Omit<CsvImportFooterProps, "onImportClick">) {
  const { t } = useTranslation();
  const ipoShares = Number(ipoSharesInput);
  const ipoListPrice = Number(ipoListPriceInput);
  const hasIpoOrder =
    ipoSharesInput.trim() !== "" && ipoListPriceInput.trim() !== "" && ipoShares > 0 && ipoListPrice > 0;
  const bufferedReserved = hasIpoOrder ? Math.round(ipoShares * ipoListPrice * 1.2 * 100) / 100 : null;

  return (
    <div className="home-journal-import__options-body">
      {(csvRowsLoaded != null || ledgerRowsCount != null) && (
        <p className="mb-3 text-xs leading-relaxed text-secondary">
          {t.home.dailyImportLoadedStats
            .replace("{csvRows}", String(csvRowsLoaded ?? "—"))
            .replace("{ledgerRows}", String(ledgerRowsCount ?? "—"))}
        </p>
      )}
      <label className="block">
        <span className="home-journal-quick__label">{t.home.dailyCashOnImport}</span>
        <input
          type="number"
          min={0}
          step="0.01"
          value={cashInput}
          onChange={(e) => onCashChange(e.target.value)}
          placeholder={t.home.dailyCashAutoPlaceholder}
          className="input-field mt-1.5 finance-value"
        />
      </label>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <label className="block">
          <span className="home-journal-quick__label">{t.home.dailyIpoShares}</span>
          <input
            type="number"
            min={0}
            step="1"
            value={ipoSharesInput}
            onChange={(e) => onIpoSharesChange(e.target.value)}
            placeholder="5"
            className="input-field mt-1.5 finance-value"
          />
        </label>
        <label className="block">
          <span className="home-journal-quick__label">{t.home.dailyIpoListPrice}</span>
          <input
            type="number"
            min={0}
            step="0.01"
            value={ipoListPriceInput}
            onChange={(e) => onIpoListPriceChange(e.target.value)}
            placeholder="135"
            className="input-field mt-1.5 finance-value"
          />
        </label>
      </div>
      {bufferedReserved != null && (
        <p className="mt-2 text-xs text-secondary">
          {t.home.dailyIpoBufferedHint
            .replace("{shares}", String(ipoShares))
            .replace("{price}", ipoListPrice.toFixed(2))
            .replace("{reserved}", formatCurrency(bufferedReserved))}
        </p>
      )}
      <label className="mt-2 block">
        <span className="home-journal-quick__label">{t.home.dailyReservedOnImport}</span>
        <input
          type="number"
          min={0}
          step="0.01"
          value={hasIpoOrder ? String(bufferedReserved) : reservedInput}
          onChange={(e) => onReservedChange(e.target.value)}
          placeholder="0"
          readOnly={hasIpoOrder}
          className="input-field mt-1.5 finance-value"
        />
      </label>
      <label className="mt-2 flex cursor-pointer items-start gap-2 text-xs text-secondary">
        <input
          type="checkbox"
          checked={replaceImport}
          onChange={(e) => onReplaceChange(e.target.checked)}
          className="mt-0.5"
        />
        <span>{t.home.dailyImportReplaceLabel}</span>
      </label>
      <GhostButton
        onClick={onSaveBuyingPower}
        disabled={savingCash || importing || !cashInput.trim()}
        className="mt-2 w-full rounded-lg px-3 py-1.5 text-xs"
      >
        {savingCash ? t.common.running : t.home.dailySaveBuyingPower}
      </GhostButton>
      {lastImport && (
        <dl className="mt-3 space-y-1 border-t border-white/5 pt-3 text-xs text-secondary">
          <div className="flex justify-between gap-3">
            <dt>{t.home.dailyImportRows}</dt>
            <dd className="finance-value text-zinc-200">{lastImport.trades_parsed}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>{t.home.dailyImportOpen}</dt>
            <dd className="finance-value text-zinc-200">{lastImport.holdings_count}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}

/** Compact CSV import row — lives below the home trade journal. */
export function CsvImportFooter(props: CsvImportFooterProps) {
  const { t } = useTranslation();
  const { onImportClick, importing } = props;

  return (
    <div className="rounded-2xl border border-zinc-800/80 bg-zinc-950/40 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <PrimaryButton
          onClick={onImportClick}
          disabled={importing}
          size="sm"
          className="rounded-xl shadow-[0_0_20px_-8px_rgba(56,189,248,0.45)]"
        >
          {importing ? t.common.running : t.home.dailyImportCsv}
        </PrimaryButton>
        <details className="group/details">
          <summary className="cursor-pointer list-none rounded-full border border-zinc-700/80 bg-zinc-900/50 px-3 py-1.5 text-xs font-medium text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200 [&::-webkit-details-marker]:hidden">
            {t.home.journalImportOptions}
          </summary>
          <div className="mt-3 rounded-xl border border-zinc-800/80 bg-zinc-950/60 p-3">
            <CsvImportOptions {...props} />
          </div>
        </details>
      </div>
      <p className="ledger-hint mt-3">{t.home.dailyCsvWhereHint}</p>
    </div>
  );
}

export function CsvImportPanel(props: CsvImportFooterProps) {
  return <CsvImportFooter {...props} />;
}

export function PennyOpportunitiesPanel({ items }: { items: PennyOpportunityItem[] }) {
  const { t } = useTranslation();
  if (!items.length) return null;

  return (
    <SectionCard
      title={t.home.dailyPennyOpsTitle}
      subtitle={t.home.dailyPennyOpsNote}
      variant="muted"
      action={
        <Link href="/scan?bucket=penny" className="text-xs font-medium text-primary hover:underline">
          {t.home.openScan}
        </Link>
      }
    >
      <ul className="space-y-2">
        {items.map((p) => (
          <li key={p.symbol} className="rounded-xl border border-white/5 px-3 py-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <Link href={`/workspace?symbol=${p.symbol}`} className="font-semibold text-primary hover:underline">
                {p.symbol}
              </Link>
              <span className="finance-value text-xs text-tertiary">
                {p.score.toFixed(0)} · {formatCurrency(p.price)}
                {p.setup_type ? ` · ${p.setup_type}` : ""}
              </span>
            </div>
            {p.summary && <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-secondary">{p.summary}</p>}
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

export function ClosedPositionsPanel({
  closed,
}: {
  closed: Array<{
    symbol: string;
    total_bought: number;
    total_sold: number;
    realized_pl: number;
    last_activity?: string;
  }>;
}) {
  const { t } = useTranslation();
  if (!closed.length) return null;

  return (
    <details className="app-card app-card--muted group">
      <summary className="cursor-pointer list-none px-5 py-4 [&::-webkit-details-marker]:hidden">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-300">{t.home.dailyClosedTitle}</h2>
            <p className="mt-0.5 text-xs text-tertiary">{t.home.dailyClosedSubtitle}</p>
          </div>
          <span className="text-lg text-zinc-600 transition group-open:rotate-45" aria-hidden>
            +
          </span>
        </div>
      </summary>
      <div className="border-t border-white/5 px-5 pb-4 pt-2">
        <div className="space-y-2 md:hidden">
          {closed.map((c) => (
            <div key={c.symbol} className="rounded-lg border border-white/5 px-3 py-2.5 text-sm">
              <div className="flex justify-between font-medium text-zinc-300">
                <span>{c.symbol}</span>
                <span className={c.realized_pl >= 0 ? "text-positive" : "text-negative"}>{formatCurrency(c.realized_pl)}</span>
              </div>
              <p className="mt-1 text-xs text-tertiary">{c.last_activity || "—"}</p>
            </div>
          ))}
        </div>
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-label-caps">
                <th className="py-2 pr-3">{t.portfolio.dailyColSymbol}</th>
                <th className="py-2 pr-3 text-right">{t.home.dailyColRealizedPl}</th>
                <th className="py-2">{t.home.dailyColLastActivity}</th>
              </tr>
            </thead>
            <tbody>
              {closed.map((c) => (
                <tr key={c.symbol} className="border-t border-white/5 text-secondary">
                  <td className="py-2.5 pr-3 font-medium text-zinc-300">{c.symbol}</td>
                  <td className={`py-2.5 pr-3 text-right finance-value ${c.realized_pl >= 0 ? "text-positive" : "text-negative"}`}>
                    {formatCurrency(c.realized_pl)}
                  </td>
                  <td className="py-2.5 text-xs">{c.last_activity || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  );
}
