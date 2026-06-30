"use client";

import Link from "next/link";
import type { AnalyzeWatchlistRow, WatchlistItem } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { PrimaryButton } from "@/components/ui/buttons";
import { useTranslation } from "@/lib/i18n";

interface WorkspaceEmptyPanelProps {
  items: WatchlistItem[];
  matrixBySymbol: Map<string, AnalyzeWatchlistRow>;
  onSelect: (symbol: string) => void;
  onToggleImport: () => void;
}

export function WorkspaceEmptyPanel({
  items,
  matrixBySymbol,
  onSelect,
  onToggleImport,
}: WorkspaceEmptyPanelProps) {
  const { t } = useTranslation();
  const preview = items.slice(0, 8);

  return (
    <div className="workspace-empty flex flex-1 flex-col gap-4 p-4 md:p-6">
      <EmptyState
        title={t.workspace.emptyTitle}
        message={t.workspace.selectFromWatchlist}
        action={
          <div className="flex flex-wrap items-center justify-center gap-2">
            <PrimaryButton size="sm" onClick={onToggleImport}>
              {t.workspace.importWatchlist}
            </PrimaryButton>
            <Link href="/scan?bucket=penny" className="btn-secondary inline-flex items-center px-3.5 py-2 text-sm font-medium">
              {t.workspace.browseScan}
            </Link>
          </div>
        }
      />

      {preview.length > 0 && (
        <section className="workspace-empty__preview mx-auto w-full max-w-2xl">
          <h2 className="text-label-caps mb-2">{t.workspace.watchlistPreview}</h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {preview.map((item) => {
              const row = matrixBySymbol.get(item.symbol.toUpperCase());
              return (
                <li key={item.symbol}>
                  <button
                    type="button"
                    onClick={() => onSelect(item.symbol)}
                    className="workspace-empty__symbol-btn flex w-full items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2.5 text-left transition hover:border-primary/40 hover:bg-primary/5"
                  >
                    <span>
                      <span className="font-mono text-sm font-semibold text-foreground">{item.symbol}</span>
                      <span className="ml-2 text-xs text-tertiary">{item.bucket}</span>
                    </span>
                    {row?.score != null && (
                      <span className="finance-value text-sm text-secondary">{row.score.toFixed(0)}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
