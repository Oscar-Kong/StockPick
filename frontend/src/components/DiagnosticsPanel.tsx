"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { SymbolDiagnosticsResponse } from "@/lib/types";
import clsx from "clsx";
import { AsyncSection, fmtNum, fmtPct } from "./AsyncSection";

interface DiagnosticsPanelProps {
  data: SymbolDiagnosticsResponse | null;
  loading: boolean;
  error: string | null;
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

export function DiagnosticsPanel({ data, loading, error }: DiagnosticsPanelProps) {
  const { t } = useTranslation();

  const state = loading ? "loading" : error ? "error" : !data ? "idle" : !data.sufficient_data ? "empty" : "ready";

  return (
    <AsyncSection
      state={state}
      loadingText={t.diagnostics.loading}
      errorText={error}
      emptyText={t.diagnostics.insufficientData}
    >
      {data && (
        <div className="space-y-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={clsx(
                "rounded-md border px-2 py-0.5 font-medium capitalize",
                data.interpretation === "high tail risk"
                  ? "border-red-500/40 text-red-300"
                  : data.interpretation === "possible momentum"
                    ? "border-emerald-500/30 text-emerald-300"
                    : data.interpretation === "possible mean reversion"
                      ? "border-sky-500/30 text-sky-300"
                      : "border-zinc-600 text-zinc-300"
              )}
            >
              {interpretationLabel(data.interpretation, t.diagnostics)}
            </span>
            <span className="text-zinc-500">
              {fmt(t.diagnostics.observations, {
                returns: data.return_bars,
                prices: data.price_bars,
              })}
            </span>
            {data.data_source !== "none" && (
              <span className="text-[10px] text-zinc-600">{data.data_source}</span>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
            <div>
              <dt className="text-zinc-500">{t.diagnostics.meanReturn}</dt>
              <dd className="font-semibold tabular-nums text-zinc-100">{fmtNum(data.mean, 4)}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">{t.diagnostics.annVol}</dt>
              <dd className="font-semibold tabular-nums text-zinc-100">
                {fmtPct(data.annualized_volatility)}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">{t.diagnostics.skewness}</dt>
              <dd className="font-semibold tabular-nums text-zinc-100">{fmtNum(data.skewness, 3)}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">{t.diagnostics.excessKurtosis}</dt>
              <dd className="font-semibold tabular-nums text-zinc-100">
                {fmtNum(data.excess_kurtosis, 3)}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">{t.diagnostics.autocorrLag1}</dt>
              <dd className="font-semibold tabular-nums text-zinc-100">
                {fmtNum(data.autocorrelation?.lag1 ?? null, 3)}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">{t.diagnostics.stationarity}</dt>
              <dd className="font-semibold text-zinc-100">
                {Boolean(data.adf?.available)
                  ? fmt(t.diagnostics.adfResult, {
                      stat: fmtNum(data.adf.statistic as number | undefined, 2),
                      p: fmtNum(data.adf.pvalue as number | undefined, 3),
                    })
                  : t.diagnostics.adfUnavailable}
              </dd>
            </div>
          </dl>

          {Boolean(data.jarque_bera?.available) && (
            <p className="text-zinc-500">
              {fmt(t.diagnostics.jarqueBera, {
                p: fmtNum(data.jarque_bera.pvalue as number | undefined, 3),
              })}
            </p>
          )}

          {data.notes.length > 0 && (
            <ul className="list-inside list-disc text-zinc-600">
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
