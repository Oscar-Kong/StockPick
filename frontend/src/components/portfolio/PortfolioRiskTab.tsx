"use client";

import type { ReactNode } from "react";
import type { FactorExposureResponse, PortfolioSummaryResponse } from "@/lib/types";
import {
  betaBadgeClass,
  betaTextClass,
  concentrationBarClass,
  concentrationStats,
  concentrationTextClass,
  effectiveBetsTextClass,
} from "@/lib/portfolioRiskColors";
import { bucketExposure } from "@/lib/portfolioUtils";
import { PortfolioCorrelationHeatmap } from "./PortfolioCorrelationHeatmap";
import { PortfolioFactorExposurePanel } from "@/components/PortfolioFactorExposurePanel";
import { fmtPct } from "@/components/AsyncSection";
import { useTranslation } from "@/lib/i18n";

const CONCENTRATION_WEIGHT_THRESHOLD = 0.25;
const PC1_VARIANCE_THRESHOLD = 0.45;
const HIGH_BETA_THRESHOLD = 1.3;

type WarningKind = "concentration" | "beta" | "pca" | "stale";

interface PortfolioRiskTabProps {
  summary: PortfolioSummaryResponse | null;
  exposureResult: FactorExposureResponse | null;
  exposureLoading: boolean;
  exposureError: string | null;
  exposureStale: boolean;
  exposureKey: string;
  onRunExposure: () => void;
  symbolsCount: number;
}

function warningStyle(kind: WarningKind): string {
  switch (kind) {
    case "concentration":
      return "border-red-500/35 bg-red-500/10 text-red-100";
    case "beta":
      return "border-orange-500/35 bg-orange-500/10 text-orange-100";
    case "pca":
      return "border-amber-500/35 bg-amber-500/10 text-amber-100";
    case "stale":
      return "border-zinc-500/35 bg-zinc-800/60 text-zinc-300";
  }
}

function MetricCard({
  label,
  value,
  sub,
  accentClass,
  barPct,
  barClass,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  accentClass?: string;
  barPct?: number;
  barClass?: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-800/80 bg-zinc-950/40 p-2.5">
      <dt className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className={`mt-0.5 text-sm font-semibold tabular-nums ${accentClass ?? "text-zinc-100"}`}>
        {value}
      </dd>
      {sub && <p className="mt-0.5 text-[10px] text-zinc-500">{sub}</p>}
      {barPct != null && barClass && (
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
          <div
            className={`h-full rounded-full transition-all ${barClass}`}
            style={{ width: `${Math.min(100, Math.max(0, barPct * 100))}%` }}
          />
        </div>
      )}
    </div>
  );
}

export function PortfolioRiskTab({
  summary,
  exposureResult,
  exposureLoading,
  exposureError,
  exposureStale,
  exposureKey,
  onRunExposure,
  symbolsCount,
}: PortfolioRiskTabProps) {
  const { t } = useTranslation();
  const warnings: { kind: WarningKind; text: string }[] = [];

  if (summary?.largest_position_weight != null && summary.largest_position_weight > CONCENTRATION_WEIGHT_THRESHOLD) {
    warnings.push({
      kind: "concentration",
      text: t.portfolio.warnSinglePosition.replace("{pct}", fmtPct(summary.largest_position_weight, 0)),
    });
  }
  if (summary?.portfolio_beta != null && summary.portfolio_beta > HIGH_BETA_THRESHOLD) {
    warnings.push({
      kind: "beta",
      text: t.portfolio.warnHighBeta.replace("{beta}", summary.portfolio_beta.toFixed(2)),
    });
  }
  if (exposureResult?.concentration_warning) {
    const ratio = exposureResult.pca?.pc1_variance_ratio ?? 0;
    warnings.push({
      kind: "pca",
      text: t.portfolio.warnPcaCluster.replace("{pct}", fmtPct(ratio, 0)),
    });
  }
  if (summary?.stale) {
    warnings.push({ kind: "stale", text: t.portfolio.warnStaleData });
  }

  const weights = (summary?.positions ?? []).map((p) => p.weight ?? 0).filter((w) => w > 0);
  const { hhi, effectiveBets } = concentrationStats(weights);
  const topThreeWeight = (summary?.positions ?? [])
    .slice(0, 3)
    .reduce((s, p) => s + (p.weight ?? 0), 0);

  const buckets = summary?.positions.length ? bucketExposure(summary.positions) : [];

  return (
    <div className="space-y-4">
      {summary && (
        <>
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard
              label={t.portfolio.largestPosition}
              value={
                <>
                  {summary.largest_position ?? "—"}
                  {summary.largest_position_weight != null && (
                    <span className={`ml-1 text-xs font-normal ${concentrationTextClass(summary.largest_position_weight)}`}>
                      ({fmtPct(summary.largest_position_weight, 1)})
                    </span>
                  )}
                </>
              }
              accentClass={concentrationTextClass(summary.largest_position_weight)}
              barPct={summary.largest_position_weight ?? 0}
              barClass={concentrationBarClass(summary.largest_position_weight)}
            />
            <MetricCard
              label={t.portfolio.topThreeConcentration}
              value={fmtPct(topThreeWeight, 1)}
              accentClass={concentrationTextClass(topThreeWeight / 3)}
              barPct={topThreeWeight}
              barClass={concentrationBarClass(topThreeWeight / 3)}
            />
            <MetricCard
              label={t.portfolio.effectiveBets}
              value={effectiveBets > 0 ? effectiveBets.toFixed(1) : "—"}
              sub={hhi > 0 ? `HHI ${(hhi * 100).toFixed(0)}%` : undefined}
              accentClass={effectiveBetsTextClass(effectiveBets)}
            />
            <MetricCard
              label={t.portfolio.portfolioBeta}
              value={
                summary.portfolio_beta != null ? (
                  <span className={`inline-flex rounded px-1.5 py-0.5 text-xs ${betaBadgeClass(summary.portfolio_beta)}`}>
                    {summary.portfolio_beta.toFixed(2)}
                  </span>
                ) : (
                  "—"
                )
              }
              accentClass={betaTextClass(summary.portfolio_beta)}
            />
            <MetricCard
              label={t.portfolio.largestSector}
              value={summary.largest_sector ?? "—"}
            />
            <MetricCard
              label={t.portfolio.positionsCount}
              value={summary.active_holdings_count}
            />
          </dl>

          {summary.positions.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="label-caps">{t.portfolio.weightDistribution}</h4>
              <div className="space-y-1">
                {summary.positions.slice(0, 10).map((p) => (
                  <div key={p.symbol} className="flex items-center gap-2 text-xs">
                    <span className="w-12 shrink-0 font-medium text-zinc-300">{p.symbol}</span>
                    <div className="relative h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-zinc-800">
                      <div
                        className={`h-full rounded-full ${concentrationBarClass(p.weight)}`}
                        style={{ width: `${Math.min(100, (p.weight ?? 0) * 100)}%` }}
                      />
                    </div>
                    <span className={`w-10 shrink-0 text-right tabular-nums ${concentrationTextClass(p.weight)}`}>
                      {p.weight != null ? fmtPct(p.weight, 0) : "—"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {buckets.length > 0 && (
        <div className="space-y-1.5">
          <h4 className="label-caps">{t.portfolio.bucketExposure}</h4>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {buckets.map((b) => (
              <div key={b.bucket} className="rounded-lg border border-zinc-800/80 bg-zinc-950/40 p-2.5">
                <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">{b.bucket}</p>
                <p className="mt-0.5 text-sm font-semibold tabular-nums text-zinc-100">{fmtPct(b.weight, 1)}</p>
                {b.value > 0 && (
                  <p className="text-[10px] text-zinc-500">${b.value.toLocaleString()}</p>
                )}
              </div>
            ))}
            {summary && summary.cash_weight > 0 && (
              <div className="rounded-lg border border-zinc-800/80 bg-zinc-950/40 p-2.5">
                <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">Cash</p>
                <p className="mt-0.5 text-sm font-semibold tabular-nums text-zinc-100">
                  {fmtPct(summary.cash_weight, 1)}
                </p>
                <p className="text-[10px] text-zinc-500">${summary.cash.toLocaleString()}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <ul className="space-y-1.5">
          {warnings.map((w) => (
            <li
              key={w.text}
              className={`rounded border px-3 py-2 text-xs ${warningStyle(w.kind)}`}
            >
              {w.text}
            </li>
          ))}
        </ul>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onRunExposure}
          disabled={exposureLoading || symbolsCount < 2}
          className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
        >
          {exposureLoading ? t.common.running : t.portfolio.exposureRun}
        </button>
      </div>

      {exposureError && <p className="text-sm text-red-400">{exposureError}</p>}

      {exposureResult?.correlation && (
        <div className="surface-card p-3">
          <PortfolioCorrelationHeatmap correlation={exposureResult.correlation} />
        </div>
      )}

      <PortfolioFactorExposurePanel
        data={exposureResult}
        loading={exposureLoading}
        error={exposureError}
        symbolsKey={exposureKey}
        stale={exposureStale}
        analytical
      />

      {exposureResult?.pca?.pc1_variance_ratio != null &&
        exposureResult.pca.pc1_variance_ratio > PC1_VARIANCE_THRESHOLD && (
          <p className="rounded border border-amber-500/25 bg-amber-500/8 px-3 py-2 text-xs text-amber-100/90">
            {t.portfolio.pcaPlainLanguage}
          </p>
        )}
    </div>
  );
}
