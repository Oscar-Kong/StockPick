"use client";

import {
  createLedgerEntry,
  deleteLedgerEntry,
  getPortfolioLedger,
  rebuildPortfolioLedger,
  updateLedgerEntry,
} from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import { compareLedgerRowsDesc } from "@/lib/datetime";
import type { LedgerEntry, LedgerEntryInput, LedgerListResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PrimaryButton } from "@/components/ui/buttons";
import {
  LedgerActionButton,
  LedgerFormField,
  LedgerGlassCard,
  LedgerHoldingsStrip,
  LedgerSidePill,
  LedgerSideToggle,
  LedgerStatusBadge,
  LedgerTableShell,
  LedgerToolbar,
  LedgerToolbarButton,
  ledgerInputClass,
  ledgerSelectClass,
} from "@/components/portfolio/ledger-ui";

type Draft = Partial<LedgerEntryInput>;

function sideLabel(side: string, t: ReturnType<typeof useTranslation>["t"]): string {
  const s = side.toLowerCase();
  if (s === "buy") return t.portfolio.sideBuy;
  if (s === "sell") return t.portfolio.sideSell;
  return t.portfolio.sideEvent;
}

function sourceLabel(source: string, t: ReturnType<typeof useTranslation>["t"]): string {
  if (source === "csv") return t.portfolio.sourceCsv;
  if (source === "journal") return t.portfolio.sourceJournal;
  return t.portfolio.sourceManual;
}

function formatAmount(side: string, qty: number | null | undefined, price: number | null | undefined): number | null {
  if (qty == null || price == null || qty === 0 || price === 0) return null;
  const gross = qty * price;
  return side.toLowerCase() === "sell" ? gross : -gross;
}

interface PortfolioLedgerPanelProps {
  onChanged?: () => void;
}

export function PortfolioLedgerPanel({ onChanged }: PortfolioLedgerPanelProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<LedgerListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | "new" | "rebuild" | null>(null);
  const [showEvents, setShowEvents] = useState(false);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [newRow, setNewRow] = useState<Draft>({
    symbol: "",
    side: "buy",
    quantity: null,
    price: null,
    amount: null,
    activity_date: "",
    trans_code: "MANUAL",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getPortfolioLedger());
    } catch (e) {
      setError(parseApiError(e, t.portfolio.ledgerLoadFailed));
    } finally {
      setLoading(false);
    }
  }, [t.portfolio.ledgerLoadFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(() => {
    const all = data?.rows ?? [];
    const filtered = showEvents
      ? all
      : all.filter((r) => r.row_type === "buy" || r.row_type === "sell");
    return [...filtered].sort(compareLedgerRowsDesc);
  }, [data?.rows, showEvents]);

  const draftFor = (row: LedgerEntry): Draft => ({
    symbol: row.symbol,
    side: row.side,
    quantity: row.quantity,
    price: row.price,
    amount: row.amount,
    activity_date: row.activity_date,
    process_date: row.process_date,
    trans_code: row.trans_code,
    description: row.description,
    ...drafts[row.id],
  });

  const setDraft = (id: number, patch: Draft) => {
    setDrafts((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  };

  const patchNewRow = (patch: Draft) => {
    setNewRow((prev) => {
      const next = { ...prev, ...patch };
      if ("quantity" in patch || "price" in patch || "side" in patch) {
        const auto = formatAmount(next.side ?? "buy", next.quantity, next.price);
        if (auto != null) next.amount = Math.round(auto * 100) / 100;
      }
      return next;
    });
  };

  const saveRow = async (id: number, row: LedgerEntry) => {
    setBusyId(id);
    setError(null);
    try {
      await updateLedgerEntry(id, { ...draftFor(row), lock: true });
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      await load();
      onChanged?.();
    } catch (e) {
      setError(parseApiError(e, t.portfolio.ledgerSaveFailed));
    } finally {
      setBusyId(null);
    }
  };

  const removeRow = async (id: number) => {
    setBusyId(id);
    try {
      await deleteLedgerEntry(id);
      await load();
      onChanged?.();
    } catch (e) {
      setError(parseApiError(e, t.portfolio.ledgerSaveFailed));
    } finally {
      setBusyId(null);
    }
  };

  const addRow = async () => {
    if (!newRow.symbol?.trim()) return;
    setBusyId("new");
    try {
      await createLedgerEntry(newRow as LedgerEntryInput);
      setNewRow({
        symbol: "",
        side: "buy",
        quantity: null,
        price: null,
        amount: null,
        activity_date: "",
        trans_code: "MANUAL",
      });
      await load();
      onChanged?.();
    } catch (e) {
      setError(parseApiError(e, t.portfolio.ledgerSaveFailed));
    } finally {
      setBusyId(null);
    }
  };

  const rebuild = async () => {
    setBusyId("rebuild");
    try {
      await rebuildPortfolioLedger();
      await load();
      onChanged?.();
    } catch (e) {
      setError(parseApiError(e, t.portfolio.ledgerSaveFailed));
    } finally {
      setBusyId(null);
    }
  };

  const canAdd = Boolean(newRow.symbol?.trim());

  return (
    <div className="space-y-4">
      <LedgerToolbar>
        <LedgerToolbarButton active={showEvents} onClick={() => setShowEvents((v) => !v)}>
          {showEvents ? t.portfolio.ledgerHideEvents : t.portfolio.ledgerShowEvents}
        </LedgerToolbarButton>
        <LedgerToolbarButton disabled={busyId === "rebuild"} onClick={() => void rebuild()}>
          {busyId === "rebuild" ? t.common.running : t.portfolio.ledgerRebuild}
        </LedgerToolbarButton>
      </LedgerToolbar>

      {error && <div className="ledger-notice ledger-notice--error">{error}</div>}
      <p className="ledger-hint">{t.portfolio.ledgerLockedHint}</p>

      {data && data.open_holdings.length > 0 && (
        <LedgerGlassCard accent="emerald" innerClassName="p-4">
          <LedgerHoldingsStrip title={t.portfolio.ledgerOpenHoldings} holdings={data.open_holdings} />
        </LedgerGlassCard>
      )}

      <LedgerGlassCard accent="emerald" innerClassName="p-4 sm:p-5">
        <div className="ledger-add-form__header">
          <div>
            <h3 className="ledger-add-form__title">{t.portfolio.ledgerAddRow}</h3>
            <p className="ledger-add-form__subtitle">{t.portfolio.ledgerAddRowSubtitle}</p>
          </div>
        </div>

        <div className="ledger-add-form__grid">
          <LedgerFormField label={t.portfolio.ledgerColDate} className="ledger-form-field--span-2 sm:col-span-1">
            <input
              type="text"
              placeholder="6/29/2026"
              className={ledgerInputClass}
              value={newRow.activity_date ?? ""}
              onChange={(e) => patchNewRow({ activity_date: e.target.value })}
            />
          </LedgerFormField>

          <LedgerFormField label={t.portfolio.ledgerColSymbol}>
            <input
              type="text"
              placeholder="AAPL"
              className={`${ledgerInputClass} font-mono uppercase tracking-wide`}
              value={newRow.symbol ?? ""}
              onChange={(e) => patchNewRow({ symbol: e.target.value.toUpperCase() })}
            />
          </LedgerFormField>

          <LedgerFormField label={t.portfolio.ledgerColSide}>
            <LedgerSideToggle
              value={newRow.side ?? "buy"}
              onChange={(side) => patchNewRow({ side })}
              buyLabel={t.portfolio.sideBuy}
              sellLabel={t.portfolio.sideSell}
            />
          </LedgerFormField>

          <LedgerFormField label={t.portfolio.ledgerColQty}>
            <input
              type="number"
              step="any"
              min={0}
              placeholder="10"
              className={ledgerInputClass}
              value={newRow.quantity ?? ""}
              onChange={(e) =>
                patchNewRow({ quantity: e.target.value ? Number(e.target.value) : null })
              }
            />
          </LedgerFormField>

          <LedgerFormField label={t.portfolio.ledgerColPrice}>
            <input
              type="number"
              step="any"
              min={0}
              placeholder="0.00"
              className={ledgerInputClass}
              value={newRow.price ?? ""}
              onChange={(e) => patchNewRow({ price: e.target.value ? Number(e.target.value) : null })}
            />
          </LedgerFormField>

          <LedgerFormField label={t.portfolio.ledgerColAmount}>
            <input
              type="number"
              step="any"
              placeholder="auto"
              className={`${ledgerInputClass} tabular-nums`}
              value={newRow.amount ?? ""}
              onChange={(e) =>
                patchNewRow({ amount: e.target.value ? Number(e.target.value) : null })
              }
            />
          </LedgerFormField>
        </div>

        <div className="ledger-add-form__actions">
          <PrimaryButton
            type="button"
            size="sm"
            className="min-w-[9rem] rounded-xl shadow-[0_0_24px_-8px_rgba(16,185,129,0.55)]"
            disabled={busyId === "new" || !canAdd}
            onClick={() => void addRow()}
          >
            {busyId === "new" ? t.common.running : t.portfolio.ledgerAddRow}
          </PrimaryButton>
        </div>
      </LedgerGlassCard>

      {loading ? (
        <p className="text-sm text-zinc-500">{t.common.loading}</p>
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 bg-zinc-950/40 px-4 py-8 text-center text-sm text-zinc-500">
          {t.portfolio.ledgerEmpty}
        </p>
      ) : (
        <LedgerTableShell>
          <table>
            <thead>
              <tr>
                <th>{t.portfolio.ledgerColDate}</th>
                <th>{t.portfolio.ledgerColSymbol}</th>
                <th>{t.portfolio.ledgerColSide}</th>
                <th>{t.portfolio.ledgerColQty}</th>
                <th>{t.portfolio.ledgerColPrice}</th>
                <th>{t.portfolio.ledgerColAmount}</th>
                <th>{t.portfolio.ledgerColSource}</th>
                <th>{t.portfolio.ledgerColStatus}</th>
                <th>{t.portfolio.ledgerColActions}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const d = draftFor(row);
                const isLocked = row.locked;
                return (
                  <tr key={row.id} className={isLocked ? "ledger-row--locked" : undefined}>
                    <td>
                      {isLocked ? (
                        <span className="ledger-cell-readonly text-zinc-300">{row.activity_date ?? "—"}</span>
                      ) : (
                        <input
                          className={ledgerInputClass}
                          value={d.activity_date ?? ""}
                          onChange={(e) => setDraft(row.id, { activity_date: e.target.value })}
                        />
                      )}
                    </td>
                    <td>
                      {isLocked ? (
                        <span className="ledger-cell-readonly font-mono font-semibold">{row.symbol}</span>
                      ) : (
                        <input
                          className={`${ledgerInputClass} max-w-[5rem] font-mono uppercase`}
                          value={d.symbol ?? ""}
                          onChange={(e) => setDraft(row.id, { symbol: e.target.value.toUpperCase() })}
                        />
                      )}
                    </td>
                    <td>
                      {isLocked ? (
                        <LedgerSidePill side={row.side} label={sideLabel(row.side, t)} />
                      ) : (
                        <select
                          className={ledgerSelectClass}
                          value={(d.side ?? row.side).toLowerCase()}
                          onChange={(e) => setDraft(row.id, { side: e.target.value })}
                        >
                          <option value="buy">{t.portfolio.sideBuy}</option>
                          <option value="sell">{t.portfolio.sideSell}</option>
                          <option value="event">{t.portfolio.sideEvent}</option>
                        </select>
                      )}
                    </td>
                    <td>
                      {isLocked ? (
                        <span className="ledger-cell-readonly">{row.quantity ?? "—"}</span>
                      ) : (
                        <input
                          type="number"
                          step="any"
                          className={`${ledgerInputClass} max-w-[5.5rem]`}
                          value={d.quantity ?? ""}
                          onChange={(e) =>
                            setDraft(row.id, { quantity: e.target.value ? Number(e.target.value) : null })
                          }
                        />
                      )}
                    </td>
                    <td>
                      {isLocked ? (
                        <span className="ledger-cell-readonly">${row.price ?? "—"}</span>
                      ) : (
                        <input
                          type="number"
                          step="any"
                          className={`${ledgerInputClass} max-w-[5.5rem]`}
                          value={d.price ?? ""}
                          onChange={(e) =>
                            setDraft(row.id, { price: e.target.value ? Number(e.target.value) : null })
                          }
                        />
                      )}
                    </td>
                    <td>
                      {isLocked ? (
                        <span className="ledger-cell-readonly">{row.amount ?? "—"}</span>
                      ) : (
                        <input
                          type="number"
                          step="any"
                          className={`${ledgerInputClass} max-w-[6rem]`}
                          value={d.amount ?? ""}
                          onChange={(e) =>
                            setDraft(row.id, { amount: e.target.value ? Number(e.target.value) : null })
                          }
                        />
                      )}
                    </td>
                    <td className="text-zinc-500">{sourceLabel(row.source, t)}</td>
                    <td>
                      <LedgerStatusBadge variant={isLocked ? "saved" : "draft"}>
                        {isLocked ? t.portfolio.ledgerLocked : t.portfolio.ledgerDraft}
                      </LedgerStatusBadge>
                    </td>
                    <td>
                      {!isLocked && (
                        <div className="flex flex-wrap gap-1.5">
                          <LedgerActionButton
                            variant="save"
                            disabled={busyId === row.id}
                            onClick={() => void saveRow(row.id, row)}
                          >
                            {busyId === row.id ? "…" : t.portfolio.ledgerSave}
                          </LedgerActionButton>
                          <LedgerActionButton
                            variant="delete"
                            disabled={busyId === row.id}
                            onClick={() => void removeRow(row.id)}
                          >
                            {t.portfolio.ledgerDelete}
                          </LedgerActionButton>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </LedgerTableShell>
      )}
    </div>
  );
}
