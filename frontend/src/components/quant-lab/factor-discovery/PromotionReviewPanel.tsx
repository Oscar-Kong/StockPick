"use client";

import {
  explainPromotionCandidate,
  getPromotionAudit,
  getPromotionCandidate,
  getPromotionEvidence,
  listPromotionCandidates,
  listShadowEvaluations,
  requestShadowEvaluation,
  transitionPromotionCandidate,
} from "@/lib/api/factorDiscovery/promotion";
import { parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import type { FactorPromotionCandidateDetail, FactorPromotionCandidateSummary, PromotionGateResult } from "@/lib/api/factorDiscovery/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { useCallback, useEffect, useState } from "react";

const ADVISORY_BADGE = "Research only · Does not affect live ranking · Manual integration required";

function GateVerdictChip({ verdict }: { verdict: PromotionGateResult["verdict"] }) {
  const cls =
    verdict === "pass"
      ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
      : verdict === "fail"
        ? "bg-red-500/15 text-red-700 dark:text-red-300"
        : verdict === "warning"
          ? "bg-amber-500/15 text-amber-800 dark:text-amber-200"
          : "bg-zinc-500/15 text-zinc-600 dark:text-zinc-300";
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${cls}`}>{verdict.replace("_", " ")}</span>;
}

function StatusChip({ status }: { status: string }) {
  const label = status.replace(/_/g, " ");
  return (
    <span className="rounded border border-sky-500/30 bg-sky-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-sky-800 dark:text-sky-200">
      {label}
    </span>
  );
}

export function PromotionReviewPanel() {
  const [items, setItems] = useState<FactorPromotionCandidateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<FactorPromotionCandidateDetail | null>(null);
  const [evidenceSummary, setEvidenceSummary] = useState<string | null>(null);
  const [audit, setAudit] = useState<Array<{ new_status: string; actor: string; reason: string; created_at: string }>>([]);
  const [shadowNote, setShadowNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sleeveFilter, setSleeveFilter] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const res = await listPromotionCandidates({ sleeve: sleeveFilter || undefined, limit: 100 }, signal);
      setItems(res.items);
    } catch (e) {
      if (signal?.aborted) return;
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [sleeveFilter]);

  useEffect(() => {
    const c = new AbortController();
    load(c.signal);
    return () => c.abort();
  }, [load]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setEvidenceSummary(null);
      setAudit([]);
      setShadowNote(null);
      return;
    }
    const c = new AbortController();
    Promise.all([
      getPromotionCandidate(selectedId, c.signal),
      getPromotionEvidence(selectedId, c.signal).catch(() => null),
      getPromotionAudit(selectedId, c.signal).catch(() => ({ events: [] })),
      listShadowEvaluations(selectedId, c.signal).catch(() => ({ runs: [] })),
    ]).then(([d, ev, aud, sh]) => {
      setDetail(d);
      setEvidenceSummary(ev?.summary ?? null);
      setAudit(aud.events ?? []);
      const shadowRuns = (sh as { runs?: unknown[] })?.runs ?? [];
      setShadowNote(shadowRuns.length ? `${shadowRuns.length} shadow run(s) on record` : "No shadow runs yet");
    });
    return () => c.abort();
  }, [selectedId]);

  const transition = async (target: string) => {
    if (!selectedId || !detail) return;
    setBusy(true);
    try {
      await transitionPromotionCandidate(selectedId, {
        target_status: target,
        actor: "quant_lab_user",
        reason: `Transition to ${target} from Quant Lab`,
        expected_evidence_bundle_hash: detail.evidence_bundle_hash ?? undefined,
      });
      await load();
      const refreshed = await getPromotionCandidate(selectedId);
      setDetail(refreshed);
    } catch (e) {
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      setBusy(false);
    }
  };

  const runShadow = async () => {
    if (!selectedId) return;
    setBusy(true);
    try {
      await requestShadowEvaluation(selectedId, {
        as_of_date: new Date().toISOString().slice(0, 10),
        symbols: ["AAPL", "MSFT", "NVDA"],
        actor: "quant_lab_user",
      });
      setShadowNote("Shadow evaluation requested (research only)");
    } catch (e) {
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      setBusy(false);
    }
  };

  const explain = async () => {
    if (!selectedId) return;
    setBusy(true);
    try {
      const res = (await explainPromotionCandidate(selectedId)) as { summary: string };
      setEvidenceSummary(res.summary);
    } catch (e) {
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      setBusy(false);
    }
  };

  if (loading && items.length === 0) return <LoadingSkeleton lines={6} />;
  if (error && items.length === 0) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div className="space-y-3">
      <p className="rounded border border-amber-500/30 bg-amber-500/5 px-2 py-1.5 text-xs text-amber-900 dark:text-amber-100">
        {ADVISORY_BADGE}
      </p>

      <div className="flex flex-wrap gap-2">
        <select
          className="rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-950"
          value={sleeveFilter}
          onChange={(e) => setSleeveFilter(e.target.value)}
          aria-label="Filter by sleeve"
        >
          <option value="">All sleeves</option>
          <option value="penny">Penny</option>
          <option value="compounder">Compounder</option>
        </select>
        <button type="button" className="rounded border px-2 py-1 text-sm" onClick={() => load()} disabled={busy}>
          Refresh
        </button>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No promotion candidates"
          message="Create candidates from extended staging results via the research API when governance is enabled."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-xs">
              <thead>
                <tr className="border-b text-left text-zinc-500">
                  <th className="py-1 pr-2">Factor</th>
                  <th className="py-1 pr-2">Sleeve</th>
                  <th className="py-1 pr-2">Status</th>
                  <th className="py-1 pr-2">Gates</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr
                    key={row.candidate_id}
                    className={`cursor-pointer border-b border-zinc-100 dark:border-zinc-800 ${selectedId === row.candidate_id ? "bg-zinc-50 dark:bg-zinc-900" : ""}`}
                    onClick={() => setSelectedId(row.candidate_id)}
                  >
                    <td className="py-1.5 pr-2 font-medium">{row.display_name}</td>
                    <td className="py-1.5 pr-2 capitalize">{row.sleeve}</td>
                    <td className="py-1.5 pr-2">
                      <StatusChip status={row.status} />
                    </td>
                    <td className="py-1.5 pr-2">{row.gate_overall_pass == null ? "—" : row.gate_overall_pass ? "Pass" : "Fail"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <aside className="space-y-2 rounded border border-zinc-200 p-2 dark:border-zinc-700">
            {!detail ? (
              <p className="text-xs text-zinc-500">Select a candidate to inspect gates and evidence.</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-1">
                  <h3 className="text-sm font-semibold">{detail.display_name}</h3>
                  <StatusChip status={detail.status} />
                </div>
                <p className="text-[11px] text-zinc-500">{detail.formula_reference.slice(0, 120)}</p>
                {evidenceSummary && <p className="text-xs text-zinc-700 dark:text-zinc-300">{evidenceSummary}</p>}

                {detail.latest_gate_evaluation?.gates?.length ? (
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="text-left text-zinc-500">
                        <th className="py-0.5">Gate</th>
                        <th className="py-0.5">Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.latest_gate_evaluation.gates.map((g) => (
                        <tr key={g.gate_id} className="border-t border-zinc-100 dark:border-zinc-800">
                          <td className="py-1 pr-1">{g.display_name}</td>
                          <td className="py-1">
                            <GateVerdictChip verdict={g.verdict} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : null}

                {detail.known_weaknesses?.length ? (
                  <div>
                    <p className="text-[10px] font-medium uppercase text-zinc-500">Known weaknesses</p>
                    <ul className="list-inside list-disc text-[11px] text-zinc-600 dark:text-zinc-400">
                      {detail.known_weaknesses.map((w) => (
                        <li key={w}>{w}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {shadowNote && <p className="text-[11px] text-zinc-500">Shadow: {shadowNote}</p>}

                <div className="flex flex-wrap gap-1 pt-1">
                  {detail.status === "experimental" && (
                    <button type="button" className="rounded border px-2 py-0.5 text-[11px]" disabled={busy} onClick={() => transition("staged")}>
                      Mark staged
                    </button>
                  )}
                  {detail.status === "staged" && (
                    <button type="button" className="rounded border px-2 py-0.5 text-[11px]" disabled={busy} onClick={() => transition("promotion_candidate")}>
                      Promotion candidate
                    </button>
                  )}
                  {detail.status === "promotion_candidate" && (
                    <button type="button" className="rounded border px-2 py-0.5 text-[11px]" disabled={busy} onClick={() => transition("shadow")}>
                      Enter shadow
                    </button>
                  )}
                  {(detail.status === "shadow" || detail.status === "promotion_candidate") && (
                    <button type="button" className="rounded border px-2 py-0.5 text-[11px]" disabled={busy} onClick={runShadow}>
                      Shadow eval
                    </button>
                  )}
                  {detail.status === "shadow" && detail.latest_gate_evaluation?.overall_pass && (
                    <button
                      type="button"
                      className="rounded border border-emerald-600/40 px-2 py-0.5 text-[11px] text-emerald-800 dark:text-emerald-200"
                      disabled={busy}
                      onClick={() => transition("approved_for_manual_integration")}
                    >
                      Approve for manual integration
                    </button>
                  )}
                  <button type="button" className="rounded border px-2 py-0.5 text-[11px]" disabled={busy} onClick={() => transition("rejected")}>
                    Reject
                  </button>
                  <button type="button" className="rounded border px-2 py-0.5 text-[11px]" disabled={busy} onClick={explain}>
                    Explain evidence
                  </button>
                </div>

                {audit.length > 0 && (
                  <div>
                    <p className="text-[10px] font-medium uppercase text-zinc-500">Audit</p>
                    <ul className="max-h-24 space-y-0.5 overflow-y-auto text-[10px] text-zinc-500">
                      {audit.map((e, i) => (
                        <li key={`${e.created_at}-${i}`}>
                          {e.new_status} · {e.actor}: {e.reason.slice(0, 60)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
