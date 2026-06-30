"use client";

import { approveRobinhoodCsv } from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import { compareLedgerRowsDesc } from "@/lib/datetime";
import type { BrokerageCsvImportResponse, CsvPreviewResponse, CsvPreviewRow } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { useState } from "react";
import { GhostButton, PrimaryButton } from "@/components/ui/buttons";
import {
  LedgerGlassCard,
  LedgerSidePill,
  LedgerTableShell,
  ledgerInputClass,
} from "@/components/portfolio/ledger-ui";

interface CsvImportReviewPanelProps {
  preview: CsvPreviewResponse;
  replace: boolean;
  onCancel: () => void;
  onApproved: (result: BrokerageCsvImportResponse) => void;
}

export function CsvImportReviewPanel({
  preview,
  replace,
  onCancel,
  onApproved,
}: CsvImportReviewPanelProps) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<CsvPreviewRow[]>(() =>
    [...preview.rows].sort(compareLedgerRowsDesc)
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const includedCount = rows.filter((r) => r.included).length;

  const updateRow = (clientId: string, patch: Partial<CsvPreviewRow>) => {
    setRows((prev) => prev.map((r) => (r.client_id === clientId ? { ...r, ...patch } : r)));
  };

  const approve = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await approveRobinhoodCsv({
        filename: preview.filename,
        replace,
        rows,
      });
      onApproved(result);
    } catch (e) {
      setError(parseApiError(e, t.portfolio.csvReviewApproveFailed));
    } finally {
      setBusy(false);
    }
  };

  return (
    <LedgerGlassCard accent="sky" innerClassName="p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-base font-semibold tracking-tight text-zinc-100">{t.portfolio.csvReviewTitle}</h3>
          <p className="mt-1 text-sm text-zinc-400">{t.portfolio.csvReviewSubtitle}</p>
          <div className="ledger-csv-meta">
            <span className="ledger-csv-meta__pill truncate max-w-[12rem]" title={preview.filename}>
              {preview.filename}
            </span>
            <span className="ledger-csv-meta__pill">
              {t.portfolio.csvReviewNewRows}: {preview.new_row_count}
            </span>
            <span className="ledger-csv-meta__pill">
              {t.portfolio.csvReviewExistingRows}: {preview.skipped_existing_count}
            </span>
            <span className="ledger-csv-meta__pill border-sky-500/30 text-sky-200/90">
              {t.portfolio.csvReviewIncludedCount.replace("{count}", String(includedCount))}
            </span>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <GhostButton type="button" size="sm" className="rounded-xl" onClick={onCancel}>
            {t.portfolio.csvReviewCancel}
          </GhostButton>
          <PrimaryButton
            type="button"
            size="sm"
            className="rounded-xl shadow-[0_0_24px_-8px_rgba(56,189,248,0.5)]"
            disabled={busy || includedCount === 0}
            onClick={() => void approve()}
          >
            {busy ? t.common.running : t.portfolio.csvReviewApprove}
          </PrimaryButton>
        </div>
      </div>

      {error && <div className="ledger-notice ledger-notice--error mt-4">{error}</div>}

      {preview.warnings.length > 0 && (
        <ul className="mt-4 space-y-1 rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-100/90">
          {preview.warnings.slice(0, 8).map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <div className="ledger-csv-compare mt-4">
        <div className="ledger-csv-compare__panel">
          <p className="ledger-csv-compare__title">{t.portfolio.csvReviewCurrent}</p>
          <ul className="mt-2 space-y-1 text-xs text-zinc-300">
            {preview.current_holdings.length === 0 ? (
              <li className="text-zinc-600">—</li>
            ) : (
              preview.current_holdings.map((h) => (
                <li key={h.symbol} className="tabular-nums">
                  <span className="font-mono font-medium text-zinc-100">{h.symbol}</span>{" "}
                  {h.shares} @ ${h.avg_cost.toFixed(2)}
                </li>
              ))
            )}
          </ul>
        </div>
        <div className="ledger-csv-compare__panel ledger-csv-compare__panel--projected">
          <p className="ledger-csv-compare__title">{t.portfolio.csvReviewProjected}</p>
          <ul className="mt-2 space-y-1 text-xs text-zinc-200">
            {preview.projected_holdings.length === 0 ? (
              <li className="text-zinc-600">—</li>
            ) : (
              preview.projected_holdings.map((h) => (
                <li key={h.symbol} className="tabular-nums">
                  <span className="font-mono font-medium text-zinc-100">{h.symbol}</span>{" "}
                  {h.shares} @ ${h.avg_cost.toFixed(2)}
                </li>
              ))
            )}
          </ul>
        </div>
      </div>

      <div className="mt-4 max-h-80">
        <LedgerTableShell>
          <table>
            <thead>
              <tr>
                <th>{t.portfolio.csvReviewIncluded}</th>
                <th>{t.portfolio.ledgerColDate}</th>
                <th>{t.portfolio.ledgerColSymbol}</th>
                <th>{t.portfolio.ledgerColSide}</th>
                <th>{t.portfolio.ledgerColQty}</th>
                <th>{t.portfolio.ledgerColPrice}</th>
                <th>{t.portfolio.ledgerColAmount}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.client_id}
                  className={!row.is_new ? "opacity-60" : undefined}
                >
                  <td>
                    <input
                      type="checkbox"
                      className="ledger-checkbox"
                      checked={row.included}
                      onChange={(e) => updateRow(row.client_id, { included: e.target.checked })}
                    />
                  </td>
                  <td>
                    <input
                      className={ledgerInputClass}
                      value={row.activity_date ?? ""}
                      onChange={(e) => updateRow(row.client_id, { activity_date: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className={`${ledgerInputClass} max-w-[5rem] font-mono uppercase`}
                      value={row.symbol}
                      onChange={(e) => updateRow(row.client_id, { symbol: e.target.value.toUpperCase() })}
                    />
                  </td>
                  <td>
                    <LedgerSidePill side={row.row_type} label={row.row_type} />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="any"
                      className={`${ledgerInputClass} max-w-[5.5rem]`}
                      value={row.quantity ?? ""}
                      onChange={(e) =>
                        updateRow(row.client_id, {
                          quantity: e.target.value ? Number(e.target.value) : null,
                        })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="any"
                      className={`${ledgerInputClass} max-w-[5.5rem]`}
                      value={row.price ?? ""}
                      onChange={(e) =>
                        updateRow(row.client_id, {
                          price: e.target.value ? Number(e.target.value) : null,
                        })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="any"
                      className={`${ledgerInputClass} max-w-[6rem]`}
                      value={row.amount ?? ""}
                      onChange={(e) =>
                        updateRow(row.client_id, {
                          amount: e.target.value ? Number(e.target.value) : null,
                        })
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </LedgerTableShell>
      </div>
    </LedgerGlassCard>
  );
}
