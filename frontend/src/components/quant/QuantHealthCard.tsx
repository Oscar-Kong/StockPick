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

export function QuantHealthCard({ embedded = false }: { embedded?: boolean }) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [data, setData] = useState<QuantHealthSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const Wrapper = embedded ? "div" : "section";
  const wrapperClass = embedded ? "space-y-3" : "surface-card p-4";

  return (
    <Wrapper className={wrapperClass}>
      <SectionHeader
        title={t.quantHealth.title}
        subtitle={t.quantHealth.subtitle}
        action={
          data ? (
            <HealthStatusBadge severity={data.overall} />
          ) : undefined
        }
      />

      {loading && <LoadingSkeleton lines={4} />}
      {!loading && error && <ErrorState message={error} onRetry={() => void load()} />}
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
