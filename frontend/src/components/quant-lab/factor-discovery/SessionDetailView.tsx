"use client";

import {
  advanceMiningSession,
  authorizeMiningSession,
  cancelMiningSession,
  getMiningEvents,
  getMiningSession,
  pauseMiningSession,
  resumeMiningSession,
  startMiningSession,
} from "@/lib/api/factorDiscovery/client";
import { errorNextAction, parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import { formatMiningStatus, primaryActionLabel } from "@/lib/api/factorDiscovery/formatters";
import type { MiningSessionDetail } from "@/lib/api/factorDiscovery/types";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { MetricTile } from "@/components/ui/MetricTile";
import clsx from "clsx";
import { useCallback, useEffect, useState } from "react";

const STEPS = [
  "Authorized",
  "Hypotheses",
  "Formulas",
  "Experiments",
  "Analysis",
  "Critique",
  "Revision",
  "Human review",
  "Completed",
] as const;

interface SessionDetailViewProps {
  sessionId: string;
  onBack: () => void;
}

export function SessionDetailView({ sessionId, onBack }: SessionDetailViewProps) {
  const [detail, setDetail] = useState<MiningSessionDetail | null>(null);
  const [events, setEvents] = useState<Array<{ event_id: string; event_type: string; created_at?: string | null }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [conflictMsg, setConflictMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [d, ev] = await Promise.all([getMiningSession(sessionId), getMiningEvents(sessionId)]);
      setDetail(d);
      setEvents(ev.items);
      setConflictMsg(null);
    } catch (e) {
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  const pollActive =
    detail &&
    ["RUNNING_EXPERIMENTS", "GENERATING_HYPOTHESES", "TRANSLATING_FORMULAS", "ANALYZING_RESULTS"].includes(
      detail.status
    );

  useEffect(() => {
    if (!pollActive) return;
    const id = window.setInterval(() => {
      if (document.hidden) return;
      load();
    }, 8000);
    return () => window.clearInterval(id);
  }, [pollActive, load]);

  const runMutation = async (fn: () => Promise<unknown>) => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      const parsed = parseFactorDiscoveryError(e);
      if (parsed.code === "STATE_VERSION_CONFLICT") {
        setConflictMsg(parsed.message);
        await load();
      } else {
        setError(`${parsed.message}. ${errorNextAction(parsed.code)}`);
      }
    } finally {
      setBusy(false);
    }
  };

  const primary = detail ? primaryActionLabel(detail.allowed_actions, detail.status) : null;

  const handlePrimary = () => {
    if (!detail) return;
    const v = detail.state_version;
    const actor = "quant-lab-ui";
    if (detail.allowed_actions.can_authorize) {
      const reason = window.prompt("Authorization reason:");
      if (!reason?.trim()) return;
      void runMutation(() => authorizeMiningSession(sessionId, { actor, reason, expected_state_version: v }));
    } else if (detail.allowed_actions.can_start) {
      void runMutation(() => startMiningSession(sessionId, { actor, expected_state_version: v }));
    } else if (detail.allowed_actions.can_resume) {
      void runMutation(() => resumeMiningSession(sessionId, { actor, expected_state_version: v }));
    } else if (detail.allowed_actions.can_advance) {
      void runMutation(() => advanceMiningSession(sessionId, { actor, expected_state_version: v }));
    }
  };

  if (loading && !detail) return <LoadingSkeleton lines={6} />;
  if (error && !detail) return <ErrorState message={error} onRetry={load} />;
  if (!detail) return null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <button type="button" className="text-xs text-secondary underline" onClick={onBack}>
            ← Sessions
          </button>
          <h2 className="text-base font-semibold text-foreground">{detail.session_name || detail.research_objective}</h2>
          <p className="text-xs text-secondary">{formatMiningStatus(detail.status)} · v{detail.state_version}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {primary && (
            <button type="button" className="btn-primary px-3 py-1.5 text-sm" disabled={busy} onClick={handlePrimary}>
              {primary}
            </button>
          )}
          {detail.allowed_actions.can_pause && (
            <button
              type="button"
              className="btn-secondary px-3 py-1.5 text-sm"
              disabled={busy}
              onClick={() => {
                const reason = window.prompt("Pause reason:") ?? "";
                if (!reason.trim()) return;
                void runMutation(() =>
                  pauseMiningSession(sessionId, {
                    actor: "quant-lab-ui",
                    reason,
                    expected_state_version: detail.state_version,
                  })
                );
              }}
            >
              Pause
            </button>
          )}
          {detail.allowed_actions.can_cancel && (
            <button
              type="button"
              className="btn-secondary px-3 py-1.5 text-sm text-red-300"
              disabled={busy}
              onClick={() => {
                const ok = window.confirm(
                  "Cancel this session? It becomes terminal. History remains; in-flight runs may complete independently."
                );
                if (!ok) return;
                const reason = window.prompt("Cancellation reason:") ?? "";
                void runMutation(() =>
                  cancelMiningSession(sessionId, {
                    actor: "quant-lab-ui",
                    reason,
                    expected_state_version: detail.state_version,
                  })
                );
              }}
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {conflictMsg && (
        <div className="rounded border border-amber-800 bg-amber-950/30 px-3 py-2 text-xs text-amber-100" role="alert">
          Stale state — refreshed to v{detail.state_version}. {conflictMsg}
        </div>
      )}
      {error && <ErrorState message={error} onRetry={load} />}

      <div className="flex flex-wrap gap-1 text-[10px] uppercase tracking-wide" aria-label="Workflow progress">
        {STEPS.map((s) => (
          <span key={s} className="rounded bg-zinc-900 px-1.5 py-0.5 text-secondary">
            {s}
          </span>
        ))}
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <MetricTile label="Pending reviews" value={detail.pending_approval_count} variant="compact" tone="warning" />
        <MetricTile label="Active lineages" value={detail.active_lineage_count} variant="compact" />
        <MetricTile label="Promising" value={detail.promising_candidate_count} variant="compact" tone="positive" />
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_240px]">
        <div className="space-y-3">
          <section className="rounded-lg border border-zinc-800 p-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-secondary">Lineages</h3>
            <ul className="mt-2 space-y-1 text-xs">
              {detail.lineages.length === 0 && <li className="text-tertiary">No lineages yet</li>}
              {detail.lineages.map((l) => (
                <li key={l.lineage_id} className="flex justify-between gap-2 border-b border-zinc-900 py-1">
                  <span className="truncate">{l.lineage_id}</span>
                  <span className={clsx(l.status.includes("PROMISING") && "text-emerald-300")}>
                    {l.status.replaceAll("_", " ")}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-lg border border-zinc-800 p-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-secondary">Experiments</h3>
            <ul className="mt-2 space-y-1 text-xs">
              {detail.evaluations.length === 0 && <li className="text-tertiary">No evaluations yet</li>}
              {detail.evaluations.map((e) => (
                <li key={e.evaluation_id} className="border-b border-zinc-900 py-1">
                  Run {e.run_id ?? "—"} · artifact {e.artifact_id ?? "pending"}
                </li>
              ))}
            </ul>
          </section>

          {detail.promising_candidate_count > 0 && (
            <section className="rounded-lg border border-emerald-900/40 bg-emerald-950/15 p-3 text-xs">
              <p className="font-medium text-emerald-100">Promising research evidence only</p>
              <p className="mt-1 text-emerald-100/80">Sealed test remains unopened. No lifecycle promotion.</p>
            </section>
          )}
        </div>

        <aside className="space-y-3">
          <section className="rounded-lg border border-zinc-800 p-3 text-xs">
            <h3 className="font-semibold uppercase tracking-wide text-secondary">Budget</h3>
            <dl className="mt-2 space-y-1">
              {Object.entries(detail.usage).slice(0, 6).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <dt className="text-tertiary">{k.replaceAll("_", " ")}</dt>
                  <dd>{String(v)}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section className="rounded-lg border border-zinc-800 p-3 text-xs">
            <h3 className="font-semibold uppercase tracking-wide text-secondary">Timeline</h3>
            <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto">
              {events.slice(-12).reverse().map((e) => (
                <li key={e.event_id} className="border-b border-zinc-900 py-1">
                  <span className="text-foreground">{e.event_type.replaceAll("_", " ")}</span>
                  <span className="ml-1 text-tertiary">{e.created_at?.slice(0, 16)}</span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      <p className="text-[10px] text-tertiary">
        Session {detail.session_id} · Integrity: {detail.integrity_status} · No sealed access · No production
        integration
      </p>
    </div>
  );
}
