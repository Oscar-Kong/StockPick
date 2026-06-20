"use client";

import { getQuantHealthSummary } from "@/lib/api";
import type { QuantHealthSummary } from "@/lib/types";
import { useTranslation, useTRef } from "@/lib/i18n";
import { useCallback, useEffect, useState } from "react";
import { HealthStatusBadge } from "@/components/badges/HealthStatusBadge";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import Link from "next/link";

type QuantHealthCardProps = {
  embedded?: boolean;
  summary?: QuantHealthSummary | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
};

export function QuantHealthCard({
  embedded = false,
  summary: summaryProp,
  loading: loadingProp,
  error: errorProp,
  onRetry,
}: QuantHealthCardProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [data, setData] = useState<QuantHealthSummary | null>(summaryProp ?? null);
  const [loading, setLoading] = useState(loadingProp ?? summaryProp === undefined);
  const [error, setError] = useState<string | null>(errorProp ?? null);
  const controlled = summaryProp !== undefined;

  const load = useCallback(async () => {
    if (controlled) return;
    setLoading(true);
    setError(null);
    try {
      setData(await getQuantHealthSummary());
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.quantHealth.loadFailed);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [controlled, tRef]);

  useEffect(() => {
    if (controlled) {
      setData(summaryProp);
      setLoading(loadingProp ?? false);
      setError(errorProp ?? null);
      return;
    }
    void load();
  }, [controlled, summaryProp, loadingProp, errorProp, load]);

  const Wrapper = embedded ? "div" : "section";
  const wrapperClass = embedded ? "space-y-3" : "surface-card p-4";

  return (
    <Wrapper className={wrapperClass}>
      <SectionHeader
        title={t.quantHealth.title}
        subtitle={t.quantHealth.subtitle}
        action={data ? <HealthStatusBadge severity={data.overall} /> : undefined}
      />

      {loading && <LoadingSkeleton lines={4} />}
      {!loading && error && (
        <ErrorState message={error} onRetry={onRetry ? () => void onRetry() : () => void load()} />
      )}
      {!loading && !error && data && (
        <div className="space-y-3">
          <ul className="space-y-2">
            {data.sections.slice(0, 6).map((section) => (
              <li
                key={section.id}
                className="flex items-start justify-between gap-3 rounded-md border border-zinc-800/80 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="text-xs font-medium text-zinc-300">{section.label}</p>
                  <p className="text-xs text-zinc-500">{section.message}</p>
                </div>
                <HealthStatusBadge severity={section.severity} className="shrink-0" />
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-3 text-xs">
            <Link href="/quant-lab?tab=data-quality" className="text-[#7dff8e] hover:underline">
              {t.quantHealth.openQuantLab}
            </Link>
            <Link href="/settings" className="text-zinc-400 hover:text-zinc-200">
              {t.quantHealth.openSettings}
            </Link>
          </div>
        </div>
      )}
    </Wrapper>
  );
}
