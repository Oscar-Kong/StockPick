"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import {
  betaTextClass,
  loadingValueClass,
  pcVarianceBarClass,
  pcVarianceChipClass,
} from "@/lib/portfolioRiskColors";
import type { FactorExposureResponse } from "@/lib/types";
import { AsyncSection, fmtNum, fmtPct } from "./AsyncSection";

interface PortfolioFactorExposurePanelProps {
  data: FactorExposureResponse | null;
  loading: boolean;
  error: string | null;
  symbolsKey: string;
  stale?: boolean;
  analytical?: boolean;
}

export function PortfolioFactorExposurePanel({
  data,
  loading,
  error,
  symbolsKey,
  stale,
  analytical = false,
}: PortfolioFactorExposurePanelProps) {
  const { t } = useTranslation();
  const state = loading ? "loading" : error ? "error" : !data ? "idle" : "ready";
  const pca = data?.pca;
  const loadings = pca?.symbol_loadings ?? [];
  const pcKeys =
    loadings.length > 0
      ? Object.keys(loadings[0]).filter((k) => k.startsWith("pc"))
      : [];

  return (
    <AsyncSection
      state={state}
      loadingText={t.portfolio.exposureLoading}
      errorText={error}
      emptyText={t.portfolio.exposureIdle}
    >
      {data && (
        <div className={`space-y-3 text-xs ${analytical ? "surface-card p-3" : ""}`}>
          {stale && (
            <p className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-100/90">
              {t.portfolio.exposureStale}
            </p>
          )}

          <p className="text-zinc-400">
            {fmt(t.portfolio.exposureBasket, { symbols: data.symbols_used.join(", ") })}
            {" · "}
            <span className="text-sky-400/90">{data.benchmark}</span>
            {" · "}
            {data.lookback_period} · n={data.observation_count}
          </p>

          {data.concentration_warning && (
            <p className="rounded border border-red-500/35 bg-red-500/10 px-2 py-1 text-red-200">
              {fmt(t.portfolio.pcaConcentrationWarning, {
                ratio: fmtPct(pca?.pc1_variance_ratio ?? null, 1),
                threshold: fmtPct(pca?.pc1_concentration_threshold ?? null, 0),
              })}
            </p>
          )}

          {pca?.explained_variance_ratio && pca.explained_variance_ratio.length > 0 && (
            <div>
              <h4 className="label-caps mb-2">{t.portfolio.explainedVariance}</h4>
              <div className="space-y-1.5">
                {pca.explained_variance_ratio.map((ratio, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span
                      className={`w-14 shrink-0 rounded border px-1.5 py-0.5 text-center tabular-nums ${pcVarianceChipClass(ratio, i)}`}
                    >
                      PC{i + 1}
                    </span>
                    <div className="relative h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-zinc-800">
                      <div
                        className={`h-full rounded-full ${pcVarianceBarClass(ratio, i)}`}
                        style={{ width: `${Math.min(100, ratio * 100)}%` }}
                      />
                    </div>
                    <span className="w-10 shrink-0 text-right tabular-nums text-zinc-400">
                      {fmtPct(ratio, 1)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!pca?.sufficient && (
            <p className="text-zinc-500">{t.portfolio.pcaInsufficient}</p>
          )}

          {loadings.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[280px] text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-zinc-500">
                    <th className="py-1 pr-2">{t.common.symbol}</th>
                    {pcKeys.map((k) => (
                      <th key={k} className="py-1 pr-2">
                        {k.toUpperCase()}
                      </th>
                    ))}
                    <th className="py-1">{t.portfolio.betaVsBench}</th>
                    {analytical && <th className="py-1">{t.portfolio.rSquared}</th>}
                  </tr>
                </thead>
                <tbody>
                  {loadings.map((row) => {
                    const sym = String(row.symbol);
                    const betaInfo = data.betas[sym];
                    const beta = betaInfo?.beta;
                    const r2 = betaInfo?.r_squared;
                    return (
                      <tr key={sym} className="border-t border-zinc-800">
                        <td className="py-1.5 font-medium text-zinc-100">{sym}</td>
                        {pcKeys.map((k) => {
                          const val = row[k] as number | undefined;
                          return (
                            <td
                              key={k}
                              className={`py-1.5 tabular-nums ${analytical ? loadingValueClass(val) : "text-zinc-300"}`}
                            >
                              {fmtNum(val, 3)}
                            </td>
                          );
                        })}
                        <td className={`py-1.5 tabular-nums font-medium ${betaTextClass(beta)}`}>
                          {beta != null ? beta.toFixed(2) : "—"}
                        </td>
                        {analytical && (
                          <td className="py-1.5 tabular-nums text-zinc-400">
                            {r2 != null ? `${(r2 * 100).toFixed(0)}%` : "—"}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {data.excluded.length > 0 && (
            <p className="text-amber-300/90">
              {t.portfolio.excludedHistory} {data.excluded.join(", ")}
            </p>
          )}

          {data.notes.length > 0 && (
            <ul className="list-inside list-disc text-zinc-600">
              {data.notes.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          )}

          <p className="text-xs text-zinc-600">
            {t.portfolio.exposureDiagnosticOnly} · key={symbolsKey}
          </p>
        </div>
      )}
    </AsyncSection>
  );
}
