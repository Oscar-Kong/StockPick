// Home — retail pro hub with quick jump and resume.
"use client";

import { HomeQuickActions } from "@/components/dashboard/HomeQuickActions";
import { HomeRegimeCard } from "@/components/dashboard/HomeRegimeCard";
import { HomeScanSummary } from "@/components/dashboard/HomeScanSummary";
import { HomePredictionCard } from "@/components/dashboard/HomePredictionCard";
import { MetricCard } from "@/components/ui/MetricCard";
import { QuantHealthCard } from "@/components/quant/QuantHealthCard";
import { getSavedProgressSummary } from "@/lib/api";
import type { SavedProgressSummary } from "@/lib/types";
import { formatDateTime } from "@/lib/datetime";
import { useTranslation } from "@/lib/i18n";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

function fmtWhen(value?: string | null): string {
  return formatDateTime(value);
}

export function HomeDashboard() {
  const { t } = useTranslation();
  const router = useRouter();
  const routes = [
    { href: "/workspace", title: t.nav.workspace, hint: t.home.routeWorkspaceHint, accent: true },
    { href: "/scan", title: t.nav.scan, hint: t.home.routeScanHint },
    { href: "/portfolio", title: t.nav.portfolio, hint: t.home.routePortfolioHint },
    { href: "/quant-lab", title: t.nav.quantLab, hint: t.home.routeQuantLabHint },
    { href: "/library", title: t.nav.library, hint: t.home.routeLibraryHint },
    { href: "/trader-intel", title: t.nav.traderIntel, hint: t.home.routeTraderIntelHint },
  ] as const;
  const [summary, setSummary] = useState<SavedProgressSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ticker, setTicker] = useState("");

  useEffect(() => {
    getSavedProgressSummary()
      .then(setSummary)
      .catch(() => setError(t.home.loadSummaryFailed));
  }, []);

  function onTickerSubmit(e: FormEvent) {
    e.preventDefault();
    const sym = ticker.trim().toUpperCase();
    if (sym) router.push(`/workspace?symbol=${encodeURIComponent(sym)}`);
  }

  const hasResume =
    summary?.latest_analyze_symbol ||
    summary?.latest_scan_bucket ||
    summary?.latest_report_symbol;

  return (
    <div className="home">
      <div className="home-top">
        <section className="home-hero">
          <p className="home-hero-badge">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#00c805]" />
            {t.home.badge}
          </p>
          <h1>{t.home.title}</h1>
          <p className="home-lead">{t.home.lead}</p>
          <form className="home-ticker-form" onSubmit={onTickerSubmit}>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder={t.home.tickerPlaceholder}
              className="input-field home-ticker-input"
              aria-label={t.common.tickerSymbol}
            />
            <button type="submit" className="btn-primary shrink-0 px-5 py-2.5 text-sm">
              {t.home.research}
            </button>
          </form>
          <p className="home-hero-tip">
            {t.home.tip.split("⌘K")[0]}
            <kbd className="command-kbd">⌘K</kbd>
            {t.home.tip.split("⌘K")[1]}
          </p>
        </section>

        <nav className="home-routes" aria-label={t.common.quickLinks}>
          {routes.map((r) => (
            <Link
              key={r.href}
              href={r.href}
              className={`home-route surface-card ${"accent" in r && r.accent ? "home-route--accent" : ""}`}
            >
              <span className="home-route-title">{r.title}</span>
              <span className="text-xs text-zinc-500">{r.hint}</span>
            </Link>
          ))}
        </nav>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <HomeQuickActions />

      <div className="grid gap-4 lg:grid-cols-2">
        <QuantHealthCard />
        <HomeRegimeCard />
      </div>

      <HomeScanSummary />
      <HomePredictionCard />

      <div className={`home-bottom${hasResume && summary ? "" : " home-bottom--full"}`}>
      <div className="home-stats">
        {(
          [
            [t.home.statScans, summary?.scan_count, t.home.statScansHint],
            [t.home.statAnalyze, summary?.analyze_count, t.home.statAnalyzeHint],
            [t.home.statReports, summary?.report_count, t.home.statReportsHint],
            [t.home.statTrades, summary?.trade_count, t.home.statTradesHint],
          ] as const
        ).map(([label, n, hint]) => (
          <MetricCard
            key={label}
            label={label}
            value={<span className="tabular-nums">{n ?? "—"}</span>}
            hint={hint}
            tone={n != null && n > 0 ? "ok" : "default"}
            className="home-stat"
          />
        ))}
      </div>

      {hasResume && summary && (
        <section className="home-resume surface-card">
          <h2 className="text-sm font-semibold text-zinc-200">{t.home.continue}</h2>
          <ul className="home-resume-list">
            {summary.latest_analyze_symbol && (
              <li>
                {t.home.resumeAnalyze}{" "}
                <Link
                  href={`/workspace?symbol=${summary.latest_analyze_symbol}`}
                  className="font-medium text-[#7dff8e] hover:underline"
                >
                  {summary.latest_analyze_symbol}
                </Link>
                {summary.latest_analyze_bucket ? ` · ${summary.latest_analyze_bucket}` : ""}
                <span className="text-zinc-600"> · {fmtWhen(summary.latest_analyze_at)}</span>
              </li>
            )}
            {summary.latest_scan_bucket && (
              <li>
                {t.home.resumeScreen}{" "}
                <Link
                  href={`/scan?bucket=${summary.latest_scan_bucket}`}
                  className="font-medium text-[#7dff8e] hover:underline"
                >
                  {summary.latest_scan_bucket}
                </Link>
                <span className="text-zinc-600"> · {fmtWhen(summary.latest_scan_at)}</span>
              </li>
            )}
            {summary.latest_report_symbol && (
              <li>
                {t.home.resumeReport}{" "}
                <Link href="/library?tab=reports" className="font-medium text-[#7dff8e] hover:underline">
                  {summary.latest_report_symbol}
                </Link>
                <span className="text-zinc-600"> · {fmtWhen(summary.latest_report_at)}</span>
              </li>
            )}
          </ul>
        </section>
      )}
      </div>
    </div>
  );
}
