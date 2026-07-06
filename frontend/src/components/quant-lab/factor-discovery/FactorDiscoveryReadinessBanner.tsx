"use client";

import type { MiningReadiness } from "@/lib/api/factorDiscovery/types";
import { readinessEntryState } from "@/lib/api/factorDiscovery/formatters";
import clsx from "clsx";

interface FactorDiscoveryReadinessBannerProps {
  readiness: MiningReadiness | null;
  loading?: boolean;
  onOpenReadiness?: () => void;
}

export function FactorDiscoveryReadinessBanner({
  readiness,
  loading,
  onOpenReadiness,
}: FactorDiscoveryReadinessBannerProps) {
  if (loading || !readiness) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs text-secondary">
        Loading Factor Discovery readiness…
      </div>
    );
  }

  const entry = readinessEntryState(readiness);

  if (entry === "disabled") {
    return (
      <div className="rounded-lg border border-red-900/50 bg-red-950/25 px-3 py-2 text-xs" role="status">
        <p className="font-medium text-red-200">Factor Discovery is disabled</p>
        <p className="mt-1 text-red-200/80">
          Set FACTOR_RESEARCH_DATA_PROVIDER to <code className="text-red-100">historical_store</code> or{" "}
          <code className="text-red-100">fixture</code> on the backend, then complete staging preflight. Mining also
          requires FACTOR_DISCOVERY_ENABLED and FACTOR_DISCOVERY_LOOP_ENABLED.
        </p>
        {readiness.blocking_reasons.length > 0 && (
          <ul className="mt-1 list-inside list-disc text-red-200/70">
            {readiness.blocking_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  if (entry === "partial") {
    return (
      <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 px-3 py-2 text-xs" role="status">
        <p className="font-medium text-amber-100">Partially ready</p>
        <p className="mt-1 text-amber-100/80">Some workflows are blocked. Review readiness before authorizing sessions.</p>
        {readiness.blocking_reasons.length > 0 && (
          <ul className="mt-1 list-inside list-disc text-amber-100/70">
            {readiness.blocking_reasons.slice(0, 4).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
        {onOpenReadiness && (
          <button type="button" className="mt-2 text-amber-200 underline" onClick={onOpenReadiness}>
            View readiness details
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-emerald-900/40 bg-emerald-950/15 px-3 py-2 text-xs" role="status">
      <p className="font-medium text-emerald-100">Supervised research available</p>
      <p className="mt-1 text-emerald-100/80">
        Provider: {readiness.data_provider ?? "—"} · LLM: {readiness.llm_provider ?? "—"}
        {!readiness.bounded_auto_ready && (
          <span className="ml-2 rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-300">Bounded auto: not ready</span>
        )}
      </p>
      <p className="mt-1 text-emerald-100/70">
        Research evidence only — no sealed-test access, no production Scan integration, no lifecycle promotion.
      </p>
    </div>
  );
}

export function ReadinessStatusChip({
  ok,
  label,
  note,
}: {
  ok: boolean;
  label: string;
  note?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-2 border-b border-zinc-800 py-1.5 text-xs last:border-0">
      <span className="text-secondary">{label}</span>
      <span className={clsx("shrink-0 font-medium", ok ? "text-emerald-300" : "text-red-300")}>
        {ok ? "Available" : "Unavailable"}
        {note && <span className="ml-1 font-normal text-tertiary">· {note}</span>}
      </span>
    </div>
  );
}
