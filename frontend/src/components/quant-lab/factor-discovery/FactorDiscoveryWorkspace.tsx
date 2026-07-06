"use client";

import { fetchMiningReadiness, listMiningSessions } from "@/lib/api/factorDiscovery/client";
import { parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import { formatMiningStatus, pendingReviewTotal, readinessEntryState } from "@/lib/api/factorDiscovery/formatters";
import type { MiningReadiness, MiningSessionListItem } from "@/lib/api/factorDiscovery/types";
import {
  buildFactorDiscoveryHref,
  resolveFactorDiscoveryView,
  type FactorDiscoveryView,
} from "@/lib/quantLabNavigation";
import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { MetricTile } from "@/components/ui/MetricTile";
import { FactorDiscoveryReadinessBanner, ReadinessStatusChip } from "./FactorDiscoveryReadinessBanner";
import { FactorRegistryPanel } from "./FactorRegistryPanel";
import { NewResearchFlow } from "./NewResearchFlow";
import { PromotionReviewPanel } from "./PromotionReviewPanel";
import { ReviewQueuePanel } from "./ReviewQueuePanel";
import { SessionDetailView } from "./SessionDetailView";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

const VIEWS: { id: FactorDiscoveryView; label: string }[] = [
  { id: "sessions", label: "Sessions" },
  { id: "new-research", label: "New Research" },
  { id: "review-queue", label: "Review Queue" },
  { id: "factors", label: "Factors" },
  { id: "readiness", label: "Readiness" },
  { id: "promotion", label: "Promotion Review" },
];

export function FactorDiscoveryWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = resolveFactorDiscoveryView(searchParams);
  const sessionId = searchParams.get("sessionId");

  const [readiness, setReadiness] = useState<MiningReadiness | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(true);
  const [sessions, setSessions] = useState<MiningSessionListItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  const loadReadiness = useCallback(async () => {
    setReadinessLoading(true);
    try {
      setReadiness(await fetchMiningReadiness());
    } catch (e) {
      setReadiness(null);
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      setReadinessLoading(false);
    }
  }, []);

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const res = await listMiningSessions({
        status: statusFilter || undefined,
        search: search || undefined,
      });
      setSessions(res.items);
    } catch (e) {
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      setSessionsLoading(false);
    }
  }, [statusFilter, search]);

  useEffect(() => {
    loadReadiness();
  }, [loadReadiness]);

  useEffect(() => {
    if (view === "sessions" && !sessionId) loadSessions();
  }, [view, sessionId, loadSessions]);

  const setView = (next: FactorDiscoveryView) => {
    router.push(buildFactorDiscoveryHref(next));
  };

  const openSession = (id: string) => {
    router.push(buildFactorDiscoveryHref("sessions", { sessionId: id }));
  };

  const metrics = useMemo(() => {
    const active = sessions.filter((s) => !["COMPLETED", "CANCELLED", "FAILED", "BUDGET_EXHAUSTED"].includes(s.status));
    const awaiting = sessions.filter((s) => pendingReviewTotal(s.pending_reviews) > 0);
    const running = sessions.filter((s) => s.status === "RUNNING_EXPERIMENTS");
    const paused = sessions.filter((s) => s.status === "PAUSED");
    const promising = sessions.filter((s) => s.promising_candidate_count > 0);
    const failed = sessions.filter((s) => s.status === "FAILED");
    return { active: active.length, awaiting: awaiting.length, running: running.length, paused: paused.length, promising: promising.length, failed: failed.length };
  }, [sessions]);

  const entry = readiness ? readinessEntryState(readiness) : "disabled";
  const canCreate = entry === "supervised";

  return (
    <div className="space-y-3">
      <FactorDiscoveryReadinessBanner
        readiness={readiness}
        loading={readinessLoading}
        onOpenReadiness={() => setView("readiness")}
      />

      <AppTabBar aria-label="Factor Discovery views" className="overflow-x-auto">
        {VIEWS.map((v) => (
          <AppTabButton key={v.id} active={view === v.id && !sessionId} onClick={() => setView(v.id)}>
            {v.label}
          </AppTabButton>
        ))}
      </AppTabBar>

      {error && <ErrorState message={error} onRetry={() => { loadReadiness(); loadSessions(); }} />}

      {sessionId && view === "sessions" ? (
        <SessionDetailView sessionId={sessionId} onBack={() => router.push(buildFactorDiscoveryHref("sessions"))} />
      ) : view === "sessions" ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <MetricTile label="Active" value={metrics.active} variant="compact" />
            <MetricTile label="Awaiting review" value={metrics.awaiting} variant="compact" tone="warning" />
            <MetricTile label="Running" value={metrics.running} variant="compact" tone="primary" />
            <MetricTile label="Paused" value={metrics.paused} variant="compact" tone="warning" />
            <MetricTile label="Promising" value={metrics.promising} variant="compact" tone="positive" />
            <MetricTile label="Failed" value={metrics.failed} variant="compact" tone="negative" />
          </div>

          <div className="flex flex-wrap gap-2">
            <input
              className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs"
              placeholder="Search objective or ID"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search sessions"
            />
            <select
              className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by status"
            >
              <option value="">All statuses</option>
              <option value="AWAITING_AUTHORIZATION">Awaiting authorization</option>
              <option value="AWAITING_HYPOTHESIS_REVIEW">Awaiting hypothesis review</option>
              <option value="RUNNING_EXPERIMENTS">Running experiments</option>
              <option value="PAUSED">Paused</option>
              <option value="COMPLETED">Completed</option>
            </select>
            <button type="button" className="btn-secondary px-2 py-1 text-xs" onClick={loadSessions}>
              Refresh
            </button>
            {canCreate && (
              <button type="button" className="btn-primary px-2 py-1 text-xs" onClick={() => setView("new-research")}>
                New research
              </button>
            )}
          </div>

          {sessionsLoading ? (
            <LoadingSkeleton lines={5} />
          ) : sessions.length === 0 ? (
            <EmptyState title="No mining sessions" message="Create a supervised research session to begin." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-800 text-secondary">
                    <th className="py-1.5 pr-2">Session</th>
                    <th className="py-1.5 pr-2">Status</th>
                    <th className="py-1.5 pr-2">Mode</th>
                    <th className="py-1.5 pr-2">Reviews</th>
                    <th className="py-1.5 pr-2">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr
                      key={s.session_id}
                      className="cursor-pointer border-b border-zinc-900 hover:bg-zinc-900/50"
                      onClick={() => openSession(s.session_id)}
                    >
                      <td className="max-w-[200px] truncate py-2 pr-2">
                        <span className="text-foreground">{s.session_name || s.research_objective}</span>
                        <span className="mt-0.5 block text-[10px] text-tertiary">{s.session_id}</span>
                      </td>
                      <td className="py-2 pr-2">{formatMiningStatus(s.status)}</td>
                      <td className="py-2 pr-2 capitalize">{s.session_mode.replaceAll("_", " ")}</td>
                      <td className="py-2 pr-2">{pendingReviewTotal(s.pending_reviews)}</td>
                      <td className="py-2 pr-2 text-tertiary">{s.updated_at?.slice(0, 16) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : view === "new-research" ? (
        canCreate && readiness ? (
          <NewResearchFlow
            readiness={readiness}
            onCreated={(id) => openSession(id)}
            onCancel={() => setView("sessions")}
          />
        ) : (
          <EmptyState title="New research unavailable" message="Enable supervised Factor Discovery readiness first." />
        )
      ) : view === "review-queue" ? (
        <ReviewQueuePanel />
      ) : view === "factors" ? (
        <FactorRegistryPanel />
      ) : view === "promotion" ? (
        <PromotionReviewPanel />
      ) : view === "readiness" ? (
        <ReadinessPanel readiness={readiness} loading={readinessLoading} />
      ) : (
        <ReadinessPanel readiness={readiness} loading={readinessLoading} />
      )}
    </div>
  );
}

function ReadinessPanel({ readiness, loading }: { readiness: MiningReadiness | null; loading: boolean }) {
  if (loading || !readiness) return <LoadingSkeleton lines={6} />;

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <section className="rounded-lg border border-zinc-800 p-3">
        <h3 className="text-xs font-semibold uppercase text-secondary">Feature status</h3>
        <div className="mt-2">
          <ReadinessStatusChip ok={readiness.factor_discovery_enabled} label="Factor Discovery" />
          <ReadinessStatusChip ok={readiness.factor_discovery_llm_enabled} label="LLM" />
          <ReadinessStatusChip ok={readiness.mining_loop_enabled} label="Mining loop" />
          <ReadinessStatusChip ok={readiness.supervised_ready} label="Supervised mode" />
          <ReadinessStatusChip ok={readiness.bounded_auto_ready} label="Bounded auto" note="not ready in Phase 8B" />
        </div>
      </section>
      <section className="rounded-lg border border-zinc-800 p-3">
        <h3 className="text-xs font-semibold uppercase text-secondary">Restrictions</h3>
        <ul className="mt-2 list-inside list-disc text-xs text-secondary">
          <li>Sealed opening unavailable in this workspace</li>
          <li>Production Scan integration unavailable</li>
          <li>Lifecycle promotion unavailable</li>
        </ul>
      </section>
      <section className="rounded-lg border border-zinc-800 p-3 md:col-span-2">
        <h3 className="text-xs font-semibold uppercase text-secondary">Staging research readiness</h3>
        <p className="mt-1 text-[10px] text-tertiary">Not trading readiness — reproducibility audit on historical-store data only.</p>
        {readiness.staging_research_readiness ? (
          <div className="mt-2 space-y-2 text-xs">
            <p>
              Latest audit: {readiness.staging_research_readiness.latest_audit_status ?? "none"} · Staging flag:{" "}
              {readiness.staging_research_readiness.staging_enabled ? "enabled" : "disabled (default)"}
            </p>
            {readiness.staging_research_readiness.blocking_reasons.length > 0 ? (
              <ul className="list-inside list-disc text-amber-200/80">
                {readiness.staging_research_readiness.blocking_reasons.slice(0, 6).map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            ) : (
              <p className="text-emerald-200/80">No staging blockers detected in latest preflight.</p>
            )}
            <ul className="list-inside list-disc text-secondary">
              {(readiness.staging_research_readiness.limitations ?? []).map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="mt-2 text-xs text-secondary">Staging preflight unavailable.</p>
        )}
      </section>
    </div>
  );
}
