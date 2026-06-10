"use client";

import { getV2FactorPerformance } from "@/lib/api";
import { isFeatureDisabledError, parseApiError } from "@/lib/apiError";
import { useTranslation, useTRef } from "@/lib/i18n";
import {
  factorPerformanceRows,
  primaryFactorHorizon,
} from "@/lib/quantLabNormalizers";
import { isFactorIcStale } from "@/lib/quantLabStability";
import {
  computeFactorLifecycleStatus,
  computeFactorPerformanceReliability,
} from "@/lib/researchReliability";
import type { Bucket } from "@/lib/types";
import { useCallback, useEffect, useMemo, useState } from "react";
import { TooltipLabel } from "@/components/ui/TooltipLabel";
import { ResearchOnlyBadge } from "@/components/ui/ResearchOnlyBadge";
import { FactorLifecycleBadge } from "./FactorLifecycleBadge";
import { ResearchReliabilityCard } from "./ResearchReliabilityCard";
import {
  BucketSelect,
  QuantLabEmptyState,
  QuantLabTabLayout,
  StaleDataBadge,
  TabRefreshRow,
} from "./QuantLabTabShell";

export function FactorPerformanceTab() {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [data, setData] = useState<Awaited<ReturnType<typeof getV2FactorPerformance>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);
  const [sleeve, setSleeve] = useState<Bucket>("medium");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDisabled(false);
    try {
      setData(await getV2FactorPerformance({ sleeve }));
    } catch (e) {
      const msg = parseApiError(e, tRef.current.quantLab.loadFailed);
      if (isFeatureDisabledError(msg)) {
        setDisabled(true);
        setData(null);
      } else {
        setError(msg);
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  }, [sleeve]);

  useEffect(() => {
    void load();
  }, [load]);

  const factors = factorPerformanceRows(data);
  const icStale = isFactorIcStale(data?.as_of_date);
  const reliability = useMemo(
    () => computeFactorPerformanceReliability({ data, disabled, loading }),
    [data, disabled, loading]
  );

  return (
    <QuantLabTabLayout
      title={t.quantLab.tabFactorPerformance}
      description={
        <TooltipLabel label={t.quantLab.hintFactorPerformance} tooltip={t.product.factorIcTooltip} />
      }
      reliability={<ResearchReliabilityCard score={reliability} />}
      statusBadge={
        <>
          <ResearchOnlyBadge tooltip={t.product.factorIcTooltip} />
          {!loading && !error && !disabled && icStale ? (
            <StaleDataBadge asOf={data?.as_of_date} />
          ) : null}
        </>
      }
      controls={
        <div className="flex flex-wrap items-center gap-2">
          <BucketSelect
            label={t.common.bucket}
            value={sleeve}
            onChange={(v) => setSleeve(v as Bucket)}
          />
          <TabRefreshRow onRefresh={() => void load()} />
        </div>
      }
      loading={loading}
      error={error}
      onRetry={() => void load()}
      disabled={disabled}
      disabledMessage={t.quantLab.featureDisabled}
      partialWarning={icStale && !loading && !error && !disabled ? t.quantLab.staleIcWarning : null}
    >
      {data && (
        <>
          <p className="text-xs text-zinc-500">
            {t.quantLab.icAsOf}: {data.as_of_date ?? "—"}
          </p>
          {factors.length === 0 ? (
            <QuantLabEmptyState message={t.quantLab.noFactorIc} />
          ) : (
            factors.slice(0, 12).map((f, index) => {
              const h = primaryFactorHorizon(f);
              if (!h) return null;
              const lifecycle = computeFactorLifecycleStatus(f, icStale);
              return (
                <div
                  key={f.factor_id || `factor-${index}`}
                  className="rounded-lg border border-zinc-800 p-3 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <span className="font-medium text-zinc-200">{f.factor_id}</span>
                    <div className="flex flex-wrap items-center gap-2">
                      <FactorLifecycleBadge status={lifecycle} />
                      <span className="tabular-nums text-zinc-400">
                        IC {h.ic != null && Number.isFinite(h.ic) ? h.ic.toFixed(3) : "—"} · n=
                        {h.sample_n ?? "—"}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </>
      )}
    </QuantLabTabLayout>
  );
}
