"use client";

import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { TooltipLabel } from "@/components/ui/TooltipLabel";
import { getV2Regime, getV2SleeveWeights } from "@/lib/api";
import type { MarketRegimeV2, SleeveWeightsV2 } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export function HomeRegimeCard() {
  const { t } = useTranslation();
  const [regime, setRegime] = useState<MarketRegimeV2 | null>(null);
  const [weights, setWeights] = useState<SleeveWeightsV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, w] = await Promise.allSettled([
        getV2Regime(),
        getV2SleeveWeights("medium"),
      ]);
      setRegime(r.status === "fulfilled" ? r.value : null);
      setWeights(w.status === "fulfilled" ? w.value : null);
      if (r.status === "rejected" && w.status === "rejected") {
        setError(t.home.regimeUnavailable);
      }
    } finally {
      setLoading(false);
    }
  }, [t.home.regimeUnavailable]);

  useEffect(() => {
    void load();
  }, [load]);

  const topWeights = weights
    ? Object.entries(weights.weights)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 4)
    : [];

  return (
    <section className="surface-card p-4">
      <SectionHeader
        title={t.home.regimeTitle}
        subtitle={t.home.regimeSubtitle}
        action={
          <Link href="/quant-lab?tab=model-admin" className="text-xs text-zinc-400 hover:text-[#7dff8e]">
            {t.home.regimeDetails}
          </Link>
        }
      />
      {loading && <LoadingSkeleton lines={2} />}
      {!loading && error && !regime && (
        <p className="text-xs text-amber-300/90">{error}</p>
      )}
      {!loading && regime && (
        <div className="space-y-3">
          <div>
            <p className="text-xs text-zinc-500">
              <TooltipLabel label={t.home.currentRegime} tooltip={t.home.regimeTooltip} />
            </p>
            <p className="text-lg font-semibold capitalize text-zinc-100">{regime.regime.replace(/_/g, " ")}</p>
            <p className="text-xs text-zinc-500">{regime.as_of_date}</p>
          </div>
          {topWeights.length > 0 && (
            <div>
              <p className="mb-1 text-xs text-zinc-500">{t.home.topFactorWeights}</p>
              <ul className="space-y-1 text-xs text-zinc-400">
                {topWeights.map(([id, w]) => (
                  <li key={id} className="flex justify-between tabular-nums">
                    <span>{id}</span>
                    <span>{(w * 100).toFixed(1)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {!loading && error && regime && (
        <ErrorState message={error} onRetry={() => void load()} className="mt-2" />
      )}
    </section>
  );
}
