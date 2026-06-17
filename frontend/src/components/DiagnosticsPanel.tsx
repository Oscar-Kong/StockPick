"use client";

import { StatTile } from "@/components/ui/StatTile";
import { fmt, useTranslation } from "@/lib/i18n";
import type { SymbolDiagnosticsResponse } from "@/lib/types";
import clsx from "clsx";
import { AsyncSection, fmtNum, fmtPct } from "./AsyncSection";

interface DiagnosticsPanelProps {
  data: SymbolDiagnosticsResponse | null;
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
}

function interpretationLabel(
  key: string,
  labels: {
    interpNoise: string;
    interpMomentum: string;
    interpMeanReversion: string;
    interpTailRisk: string;
    interpInsufficient: string;
  }
): string {
  const map: Record<string, string> = {
    "mostly noise": labels.interpNoise,
    "possible momentum": labels.interpMomentum,
    "possible mean reversion": labels.interpMeanReversion,
    "high tail risk": labels.interpTailRisk,
    "insufficient data": labels.interpInsufficient,
  };
  return map[key] ?? key;
}

function interpretationTone(key: string): string {
  if (key === "high tail risk") return "text-red-300";
  if (key === "possible momentum") return "text-emerald-300";
  if (key === "possible mean reversion") return "text-sky-300";
  return "text-zinc-200";
}

export function DiagnosticsPanel({ data, loading, error, onRetry }: DiagnosticsPanelProps) {
  const { t } = useTranslation();

  const state = loading ? "loading" : error ? "error" : !data ? "idle" : !data.sufficient_data ? "empty" : "ready";

  return (
    <AsyncSection
      state={state}
      loadingText={t.diagnostics.loading}
      errorText={error}
      emptyText={t.diagnostics.insufficientData}
      onRetry={onRetry}
    >
      {data && (
        <div className="space-y-4">
          <dl className="stat-tile-grid grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <StatTile
              label={t.diagnostics.interpretationLabel}
              value={
                <span className={clsx("capitalize", interpretationTone(data.interpretation))}>
                  {interpretationLabel(data.interpretation, t.diagnostics)}
                </span>
              }
            />
            <StatTile
              label={t.diagnostics.observationsLabel}
              value={
                <span className="text-zinc-300">
                  {fmt(t.diagnostics.observations, {
                    returns: data.return_bars,
                    prices: data.price_bars,
                  })}
                </span>
              }
            />
            {data.data_source !== "none" && (
              <StatTile label={t.diagnostics.dataSourceLabel} value={data.data_source} />
            )}
            <StatTile
              label={t.diagnostics.meanReturn}
              value={<span className="tabular-nums">{fmtNum(data.mean, 4)}</span>}
            />
            <StatTile
              label={t.diagnostics.annVol}
              value={<span className="tabular-nums">{fmtPct(data.annualized_volatility)}</span>}
            />
            <StatTile
              label={t.diagnostics.skewness}
              value={<span className="tabular-nums">{fmtNum(data.skewness, 3)}</span>}
            />
            <StatTile
              label={t.diagnostics.excessKurtosis}
              value={<span className="tabular-nums">{fmtNum(data.excess_kurtosis, 3)}</span>}
            />
            <StatTile
              label={t.diagnostics.autocorrLag1}
              value={<span className="tabular-nums">{fmtNum(data.autocorrelation?.lag1 ?? null, 3)}</span>}
            />
            <StatTile
              label={t.diagnostics.stationarity}
              value={
                Boolean(data.adf?.available)
                  ? fmt(t.diagnostics.adfResult, {
                      stat: fmtNum(data.adf.statistic, 2),
                      p: fmtNum(data.adf.pvalue, 3),
                    })
                  : t.diagnostics.adfUnavailable
              }
            />
          </dl>

          {Boolean(data.jarque_bera?.available) && (
            <p className="text-[0.6875rem] leading-relaxed text-zinc-500">
              {fmt(t.diagnostics.jarqueBera, {
                p: fmtNum(data.jarque_bera.pvalue, 3),
              })}
            </p>
          )}

          {data.notes.length > 0 && (
            <ul className="list-inside list-disc space-y-1 text-[0.6875rem] leading-relaxed text-zinc-500">
              {data.notes.slice(0, 4).map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </AsyncSection>
  );
}
