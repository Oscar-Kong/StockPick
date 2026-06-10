"use client";

import { getQuantLabEvidence } from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import { evidenceCards } from "@/lib/quantLabLastRun";
import type { Bucket, QuantLabEvidenceResponse } from "@/lib/types";
import { useTranslation, useTRef } from "@/lib/i18n";
import { useCallback, useEffect, useState } from "react";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { QuantLabLastRunCard } from "./QuantLabLastRunCard";

type QuantLabTab =
  | "factor-performance"
  | "walk-forward"
  | "predictions"
  | "pairs"
  | "data-quality"
  | "model-admin";

interface QuantLabEvidencePanelProps {
  sleeve?: Bucket;
  onNavigateTab: (tab: QuantLabTab) => void;
}

const CARD_TITLE_KEYS = {
  factor_ic: "lastRunFactorIc",
  walk_forward: "lastRunWalkForward",
  predictions: "lastRunPredictions",
  pairs: "lastRunPairs",
  jobs: "lastRunJobs",
} as const;

export function QuantLabEvidencePanel({ sleeve = "penny", onNavigateTab }: QuantLabEvidencePanelProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [data, setData] = useState<QuantLabEvidenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getQuantLabEvidence(sleeve));
    } catch (e) {
      setData(null);
      setError(parseApiError(e, tRef.current.quantLab.loadFailed));
    } finally {
      setLoading(false);
    }
  }, [sleeve]);

  useEffect(() => {
    void load();
  }, [load]);

  const titleFor = (id: string) => {
    const key = CARD_TITLE_KEYS[id as keyof typeof CARD_TITLE_KEYS];
    return key ? (t.quantLab[key] as string) : id;
  };

  const tabFor = (tab: string | null | undefined): QuantLabTab => {
    const valid: QuantLabTab[] = [
      "factor-performance",
      "walk-forward",
      "predictions",
      "pairs",
      "data-quality",
      "model-admin",
    ];
    if (tab && valid.includes(tab as QuantLabTab)) return tab as QuantLabTab;
    return "factor-performance";
  };

  return (
    <section className="mb-4 space-y-3">
      <div className="space-y-1">
        <h2 className="text-sm font-semibold text-zinc-200">{t.quantLab.evidenceTitle}</h2>
        <p className="text-xs text-zinc-500">
          {data?.validation_copy ?? t.quantLab.validationCopy}
        </p>
      </div>

      {loading && <LoadingSkeleton lines={3} />}
      {error && !loading && <ErrorState message={error} onRetry={() => void load()} />}
      {!loading && !error && data && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {evidenceCards(data).map((summary) => (
            <QuantLabLastRunCard
              key={summary.id}
              summary={summary}
              title={titleFor(summary.id)}
              onViewDetails={() => onNavigateTab(tabFor(summary.tab))}
              onRunNew={() => onNavigateTab(tabFor(summary.tab))}
            />
          ))}
        </div>
      )}
    </section>
  );
}
