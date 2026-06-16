// Persistent right rail — key metrics visible on every analysis tab.
"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { AnalyzeSymbolResponse, Bucket, Signal, V2ScoreResponse } from "@/lib/types";
import { bucketFitDisplayOrder } from "@/lib/buckets";
import type { AnalysisDisplay } from "@/lib/v2Score";
import clsx from "clsx";
import { ScoreSourceBadge } from "./ScoreSourceBadge";
import { ValuationBadges } from "./ValuationBadges";

interface AnalysisSidebarProps {
  data: AnalyzeSymbolResponse;
  bucketFit: AnalyzeSymbolResponse["bucket_fit"];
  bucketFitLoading?: boolean;
  display?: AnalysisDisplay;
  v2Score?: V2ScoreResponse | null;
}

function SidebarSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  return (
    <details className="analysis-sidebar-section" open={defaultOpen}>
      <summary className="analysis-sidebar-section-summary">{title}</summary>
      <div className="analysis-sidebar-section-body">{children}</div>
    </details>
  );
}

function StatCell({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="analysis-stat">
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-400">{label}</dt>
      <dd className="mt-1 text-base font-semibold tabular-nums text-zinc-50">{value}</dd>
    </div>
  );
}

function SignalsList({ signals }: { signals: Signal[] }) {
  const { t } = useTranslation();
  const sorted = [...signals].sort((a, b) => b.contribution - a.contribution);
  return (
    <ul className="space-y-1.5">
      {sorted.map((s) => (
        <li key={s.name} className="rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-2 py-1.5">
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="truncate text-zinc-300">{s.name}</span>
            <span className="shrink-0 font-medium text-[#7dff8e]">{s.contribution.toFixed(1)}</span>
          </div>
          <div className="mt-1 h-1 overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full rounded-full bg-[#00c805]"
              style={{ width: `${Math.min(100, s.contribution)}%` }}
            />
          </div>
          <p className="mt-0.5 text-[10px] text-zinc-600">
            {fmt(t.analysis.signalValue, { value: s.value.toFixed(1) })}
          </p>
        </li>
      ))}
    </ul>
  );
}

function BucketFitMini({
  scores,
  assigned,
  loading,
}: {
  scores: AnalyzeSymbolResponse["bucket_fit"]["scores"];
  assigned: string;
  loading?: boolean;
}) {
  const { t } = useTranslation();
  if (loading) {
    return <p className="text-xs text-zinc-500">{t.analysis.scoringBuckets}</p>;
  }
  return (
    <div className={`grid gap-1.5 ${scores.medium != null ? "grid-cols-3" : "grid-cols-2"}`}>
      {bucketFitDisplayOrder(scores).map((b) => {
        const s = scores[b];
        const active = b === assigned;
        return (
          <div
            key={b}
            className={clsx(
              "rounded-lg border px-2 py-1.5 text-center",
              active ? "border-[#00c805]/40 bg-[#00c805]/10" : "border-zinc-800"
            )}
          >
            <p className="text-[10px] capitalize text-zinc-500">
              {b === "medium" ? `${b.slice(0, 4)}*` : b.slice(0, 4)}
            </p>
            <p className="text-sm font-semibold tabular-nums text-zinc-100">
              {s?.score?.toFixed(0) ?? "—"}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function formatFundValue(key: string, value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "number") {
    if (key === "marketCap") return `$${(value / 1e9).toFixed(1)}B`;
    if (key === "revenueGrowth" || key === "profitMargins") return `${(value * 100).toFixed(1)}%`;
    return value.toFixed(2);
  }
  return String(value);
}

export function AnalysisSidebar({
  data,
  bucketFit,
  bucketFitLoading,
  display,
  v2Score,
}: AnalysisSidebarProps) {
  const { t } = useTranslation();
  const tech = data.technicals;
  const fund = data.fundamentals ?? {};
  const scores = bucketFit?.scores ?? {};
  const primarySignals = display?.signals ?? data.signals;
  const scoreSource = display?.scoreSource ?? (v2Score ? "scoring_engine_v2" : "legacy_screener");

  const fundEntries: { label: string; value: string }[] = [];
  const labelsUsed = new Set<string>();
  for (const [key, label] of [
    ["sector", t.scan.sector],
    ["industry", t.analysis.industry],
    ["marketCap", t.analysis.mktCap],
    ["trailingPE", "P/E"],
    ["pe_ratio", "P/E"],
    ["revenueGrowth", t.analysis.revGrowth],
    ["profitMargins", t.analysis.margin],
  ] as const) {
    if (labelsUsed.has(label)) continue;
    const v = fund[key];
    if (v == null || v === "") continue;
    labelsUsed.add(label);
    fundEntries.push({ label, value: formatFundValue(key, v) });
  }

  return (
    <div className="space-y-2 p-3">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-2.5 py-2">
        <ScoreSourceBadge source={scoreSource} />
        <p className="text-[10px] leading-relaxed text-zinc-500">{t.analysis.sidebarInsightsHint}</p>
      </div>

      <SidebarSection title={t.analysis.technicals}>
        <div className="grid grid-cols-2 gap-1.5">
          <StatCell label={t.analysis.trend} value={tech.trend_score ?? "—"} />
          <StatCell label={t.analysis.rsVsSpy} value={tech.rs_vs_spy ?? "—"} />
          <StatCell label={t.analysis.breakout} value={tech.breakout_score ?? "—"} />
          <StatCell
            label={t.analysis.high52w}
            value={tech.pct_from_52w_high != null ? `${tech.pct_from_52w_high}%` : "—"}
          />
        </div>
      </SidebarSection>

      <SidebarSection title={t.analysis.qualityTiming}>
        <div className="grid grid-cols-2 gap-1.5">
          <StatCell
            label={t.analysis.dataQuality}
            value={
              data.data_quality_score != null ? `${data.data_quality_score.toFixed(0)}%` : "—"
            }
          />
          <StatCell
            label={t.analysis.earnings}
            value={
              data.days_until_earnings != null
                ? fmt(t.analysis.earningsIn, { days: data.days_until_earnings })
                : "—"
            }
          />
        </div>
        <div className="mt-2">
          <ValuationBadges
            warnings={data.valuation_warnings}
            earningsSoon={data.earnings_soon}
            earningsDate={data.earnings_date}
            daysUntil={data.days_until_earnings ?? undefined}
          />
        </div>
      </SidebarSection>

      <SidebarSection title={t.analysis.bucketFit}>
        <BucketFitMini
          scores={scores}
          assigned={data.assigned_bucket}
          loading={bucketFitLoading}
        />
      </SidebarSection>

      <SidebarSection
        title={
          scoreSource === "scoring_engine_v2" ? t.analysis.factorAttribution : t.analysis.signalWeights
        }
        defaultOpen={false}
      >
        <SignalsList signals={primarySignals} />
      </SidebarSection>

      {fundEntries.length > 0 && (
        <SidebarSection title={t.analysis.fundamentals} defaultOpen={false}>
          <dl className="space-y-1.5">
            {fundEntries.map(({ label, value }) => (
              <div key={label} className="flex justify-between gap-2 text-xs">
                <dt className="text-zinc-500">{label}</dt>
                <dd className="font-medium text-zinc-200">{value}</dd>
              </div>
            ))}
          </dl>
        </SidebarSection>
      )}
    </div>
  );
}
