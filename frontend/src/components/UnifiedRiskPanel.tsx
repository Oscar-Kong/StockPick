"use client";

import { useTranslation } from "@/lib/i18n";
import type { UnifiedRiskV2 } from "@/lib/types";
import clsx from "clsx";
import { AsyncSection, fmtNum, fmtPct } from "./AsyncSection";

interface UnifiedRiskPanelProps {
  data: UnifiedRiskV2 | null;
  loading: boolean;
  error: string | null;
}

function liquidityLines(data: UnifiedRiskV2): string[] {
  const fromCompany = data.company.filter((line) =>
    /liquidity|volume|adv|spread|thin/i.test(line)
  );
  const fromDeductions = data.score_deductions
    .filter((d) => /liquidity|volume|adv/i.test(d.category))
    .map((d) => `${d.category} (−${d.points})`);
  return [...fromCompany, ...fromDeductions];
}

export function UnifiedRiskPanel({ data, loading, error }: UnifiedRiskPanelProps) {
  const { t } = useTranslation();
  const state = loading ? "loading" : error ? "error" : !data ? "idle" : "ready";
  const vol = data?.volatility;
  const liquidity = data ? liquidityLines(data) : [];

  return (
    <AsyncSection
      state={state}
      loadingText={t.riskPanel.loading}
      errorText={error}
      emptyText={t.riskPanel.unavailable}
    >
      {data && (
        <div className="space-y-3 text-xs">
          <div className="flex flex-wrap gap-3">
            <div>
              <p className="text-zinc-500">{t.riskPanel.riskIndex}</p>
              <p
                className={clsx(
                  "text-lg font-semibold tabular-nums",
                  data.risk_index >= 65 ? "text-red-300" : data.risk_index >= 40 ? "text-amber-300" : "text-[#7dff8e]"
                )}
              >
                {data.risk_index.toFixed(0)}
              </p>
            </div>
            <div>
              <p className="text-zinc-500">{t.riskPanel.safetyScore}</p>
              <p className="text-lg font-semibold tabular-nums text-zinc-100">
                {data.safety_score.toFixed(0)}
              </p>
            </div>
            <div>
              <p className="text-zinc-500">{t.riskPanel.deductionPts}</p>
              <p className="text-lg font-semibold tabular-nums text-zinc-100">
                {data.deduction_pts.toFixed(1)}
              </p>
            </div>
          </div>

          <div>
            <h4 className="label-caps mb-1">{t.riskPanel.volatilitySection}</h4>
            {!vol?.sufficient_data ? (
              <p className="text-zinc-500">{t.riskPanel.volInsufficient}</p>
            ) : (
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
                <div>
                  <dt className="text-zinc-500">{t.riskPanel.realizedVol}</dt>
                  <dd className="font-semibold tabular-nums">{fmtPct(vol.realized_volatility)}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">{t.riskPanel.ewmaVol}</dt>
                  <dd className="font-semibold tabular-nums">{fmtPct(vol.ewma_volatility)}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">{t.riskPanel.downsideVol}</dt>
                  <dd className="font-semibold tabular-nums">{fmtPct(vol.downside_volatility)}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">{t.riskPanel.var}</dt>
                  <dd className="font-semibold tabular-nums">{fmtPct(vol.historical_var)}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">{t.riskPanel.expectedShortfall}</dt>
                  <dd className="font-semibold tabular-nums">{fmtPct(vol.historical_es)}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">{t.riskPanel.volRegime}</dt>
                  <dd className="font-semibold capitalize">{vol.volatility_regime ?? "—"}</dd>
                </div>
              </dl>
            )}
          </div>

          {data.macro.length > 0 && (
            <div>
              <h4 className="label-caps mb-1">{t.riskPanel.macro}</h4>
              <ul className="list-inside list-disc text-zinc-400">
                {data.macro.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h4 className="label-caps mb-1">{t.riskPanel.liquidityRisk}</h4>
            {liquidity.length > 0 ? (
              <ul className="list-inside list-disc text-zinc-400">
                {liquidity.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : data.company.length > 0 ? (
              <ul className="list-inside list-disc text-zinc-400">
                {data.company.slice(0, 3).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : (
              <p className="text-zinc-500">{t.riskPanel.noLiquidityFlags}</p>
            )}
          </div>

          <div>
            <h4 className="label-caps mb-1">{t.riskPanel.eventRisk}</h4>
            {data.events.length > 0 ? (
              <ul className="list-inside list-disc text-zinc-400">
                {data.events.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : (
              <p className="text-zinc-500">{t.riskPanel.noEventFlags}</p>
            )}
          </div>

          {data.alerts.length > 0 && (
            <div>
              <h4 className="label-caps mb-1">{t.riskPanel.alerts}</h4>
              <ul className="space-y-1">
                {data.alerts.map((a, i) => (
                  <li key={`${a.type}-${i}`} className="text-amber-200/90">
                    {a.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </AsyncSection>
  );
}
