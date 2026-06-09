// Saved scans and research reports in one library view.
"use client";

import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import { deleteSavedReport, deleteSavedScan, listSavedAnalyze, listSavedReports, listSavedScans, updateSavedReport } from "@/lib/api";
import { ResearchReport } from "@/components/ResearchReport";
import type { SavedAnalyzeItem, SavedReportItem, SavedScanItem, StockResearchReport } from "@/lib/types";
import clsx from "clsx";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { fmt, useTranslation } from "@/lib/i18n";
import { Suspense, useCallback, useEffect, useState } from "react";

type LibraryTab = "scans" | "reports" | "snapshots";

function LibraryContent() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab: LibraryTab =
    searchParams.get("tab") === "reports"
      ? "reports"
      : searchParams.get("tab") === "snapshots"
        ? "snapshots"
        : "scans";

  const setTab = useCallback(
    (next: LibraryTab) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", next);
      router.replace(`/library?${params.toString()}`);
    },
    [router, searchParams]
  );

  const [scans, setScans] = useState<SavedScanItem[]>([]);
  const [selectedScan, setSelectedScan] = useState<SavedScanItem | null>(null);
  const [reports, setReports] = useState<SavedReportItem[]>([]);
  const [snapshots, setSnapshots] = useState<SavedAnalyzeItem[]>([]);
  const [selectedReport, setSelectedReport] = useState<SavedReportItem | null>(null);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadScans = useCallback(async () => {
    const data = await listSavedScans();
    setScans(data);
    setSelectedScan((prev) => {
      if (prev && data.some((r) => r.id === prev.id)) return prev;
      return data[0] ?? null;
    });
  }, []);

  const loadReports = useCallback(async () => {
    const data = await listSavedReports();
    setReports(data);
    setSelectedReport((prev) => {
      if (prev && data.some((r) => r.id === prev.id)) return prev;
      return data[0] ?? null;
    });
    if (data[0]) {
      setTitle(data[0].title);
      setNotes(data[0].notes);
    }
  }, []);

  const loadSnapshots = useCallback(async () => {
    const data = await listSavedAnalyze();
    setSnapshots(data);
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadScans(), loadReports(), loadSnapshots()])
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [loadScans, loadReports, loadSnapshots]);

  useEffect(() => {
    if (!selectedReport) return;
    setTitle(selectedReport.title);
    setNotes(selectedReport.notes);
  }, [selectedReport]);

  const pickReport = (row: SavedReportItem) => {
    setSelectedReport(row);
    setTitle(row.title);
    setNotes(row.notes);
  };

  const saveReportMeta = async () => {
    if (!selectedReport) return;
    setSaving(true);
    try {
      const updated = await updateSavedReport(selectedReport.id, { title, notes });
      setSelectedReport(updated);
      setReports((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-0">
      <header className="page-toolbar shrink-0">
        <div>
          <h1>{t.library.title}</h1>
          <p className="page-toolbar-meta">
            {t.library.subtitle}{" "}
            <Link href="/workspace" className="text-[#7dff8e] underline">
              {t.library.workspaceLink}
            </Link>
          </p>
        </div>
        <AppTabBar aria-label={t.library.sectionsAria}>
          {(
            [
              ["scans", t.library.tabScans],
              ["reports", t.library.tabReports],
              ["snapshots", t.library.tabSnapshots],
            ] as const
          ).map(([id, label]) => (
            <AppTabButton key={id} active={tab === id} onClick={() => setTab(id)}>
              {label}
            </AppTabButton>
          ))}
        </AppTabBar>
      </header>

      <div className="workspace-panel-scroll min-h-0 flex-1 pt-2">
      {loading ? (
        <p className="text-sm text-zinc-500">{t.library.loading}</p>
      ) : tab === "scans" ? (
        scans.length === 0 ? (
          <div className="surface-card border-dashed p-8 text-sm text-zinc-500">
            {t.library.noScans}{" "}
            <Link href="/scan" className="underline text-[#7dff8e]">
              {t.library.scanPage}
            </Link>{" "}
            {t.library.noScansEnd}
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
            <aside className="surface-card max-h-[72vh] space-y-2 overflow-y-auto p-3">
              {scans.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setSelectedScan(r)}
                  className={clsx(
                    "w-full rounded-lg border px-3 py-2 text-left text-sm",
                    selectedScan?.id === r.id
                      ? "border-[#00c805] bg-zinc-900"
                      : "border-zinc-800 hover:bg-zinc-900/70"
                  )}
                >
                  <p className="font-medium">{r.name}</p>
                  <p className="text-xs text-zinc-500">
                    {fmt(t.library.resultCount, { bucket: r.bucket, count: r.result_count })}
                  </p>
                </button>
              ))}
            </aside>
            <section className="surface-card p-4">
              {!selectedScan ? (
                <p className="text-sm text-zinc-500">{t.library.selectScan}</p>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h2 className="text-lg font-semibold">{selectedScan.name}</h2>
                      <p className="text-xs text-zinc-500">
                        {fmt(t.library.resultCount, {
                          bucket: selectedScan.bucket,
                          count: selectedScan.result_count,
                        })}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={async () => {
                        await deleteSavedScan(selectedScan.id);
                        await loadScans();
                      }}
                      className="btn-ghost px-3 py-1 text-xs"
                    >
                      {t.common.delete}
                    </button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead className="text-left text-xs text-zinc-500">
                        <tr>
                          <th className="py-2 pr-4">{t.common.symbol}</th>
                          <th className="py-2 pr-4">{t.common.score}</th>
                          <th className="py-2">{t.common.action}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedScan.results.map((x) => (
                          <tr key={x.symbol} className="border-t border-zinc-900">
                            <td className="py-2 font-medium">{x.symbol}</td>
                            <td className="py-2">{x.score.toFixed(1)}</td>
                            <td className="py-2">
                              <Link
                                href={`/workspace?symbol=${x.symbol}`}
                                className="text-[#7dff8e] underline text-xs"
                              >
                                {t.library.openInWorkspace}
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </section>
          </div>
        )
      ) : tab === "snapshots" ? (
        snapshots.length === 0 ? (
          <div className="surface-card border-dashed p-8 text-sm text-zinc-500">{t.library.noSnapshots}</div>
        ) : (
          <div className="surface-card overflow-x-auto p-4">
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs text-zinc-500">
                <tr>
                  <th className="py-2 pr-4">{t.common.symbol}</th>
                  <th className="py-2 pr-4">{t.common.bucket}</th>
                  <th className="py-2 pr-4">{t.common.score}</th>
                  <th className="py-2">{t.common.action}</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((s) => (
                  <tr key={s.id} className="border-t border-zinc-900">
                    <td className="py-2 font-medium">{s.symbol}</td>
                    <td className="py-2">{s.bucket}</td>
                    <td className="py-2 tabular-nums">{s.score?.toFixed(1) ?? "—"}</td>
                    <td className="py-2">
                      <Link href={`/workspace?symbol=${s.symbol}`} className="text-[#7dff8e] underline text-xs">
                        {t.library.openInWorkspace}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : reports.length === 0 ? (
        <div className="surface-card border-dashed p-8 text-sm text-zinc-500">
          {t.library.noReports}
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
          <aside className="surface-card max-h-[72vh] space-y-2 overflow-y-auto p-3">
            {reports.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => pickReport(r)}
                className={clsx(
                  "w-full rounded-lg border px-3 py-2 text-left text-sm",
                  selectedReport?.id === r.id
                    ? "border-[#00c805] bg-zinc-900"
                    : "border-zinc-800 hover:bg-zinc-900/70"
                )}
              >
                <p className="font-medium">{r.title}</p>
                <p className="text-xs text-zinc-500">{r.symbol}</p>
              </button>
            ))}
          </aside>
          <section className="surface-card space-y-4 p-4">
            {selectedReport && (
              <>
                <div className="flex flex-wrap gap-2">
                  <Link
                    href={`/workspace?symbol=${selectedReport.symbol}`}
                    className="btn-primary px-3 py-1.5 text-xs"
                  >
                    {fmt(t.library.analyzeSymbol, { symbol: selectedReport.symbol })}
                  </Link>
                  <button type="button" onClick={saveReportMeta} disabled={saving} className="btn-ghost px-3 py-1.5 text-xs">
                    {saving ? t.common.saving : t.library.saveTitleNotes}
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      await deleteSavedReport(selectedReport.id);
                      await loadReports();
                    }}
                    className="btn-ghost px-3 py-1.5 text-xs"
                  >
                    {t.common.delete}
                  </button>
                </div>
                <ResearchReport report={selectedReport.report as StockResearchReport} />
              </>
            )}
          </section>
        </div>
      )}
      </div>
    </div>
  );
}

function LibraryLoading() {
  const { t } = useTranslation();
  return <p className="text-sm text-zinc-500">{t.library.loading}</p>;
}

export function LibraryPage() {
  return (
    <Suspense fallback={<LibraryLoading />}>
      <LibraryContent />
    </Suspense>
  );
}
