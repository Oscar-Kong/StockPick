"use client";

import {
  authorizeMiningSession,
  createMiningSession,
  createResearchFamily,
  listResearchFamilies,
} from "@/lib/api/factorDiscovery/client";
import { errorNextAction, parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import type { MiningReadiness, ResearchFamilyItem } from "@/lib/api/factorDiscovery/types";
import { ErrorState } from "@/components/ui/ErrorState";
import { MetricTile } from "@/components/ui/MetricTile";
import clsx from "clsx";
import { useEffect, useState } from "react";

const DEFAULT_PERIOD_SPLIT = {
  discovery_start: "2022-01-03",
  discovery_end: "2023-06-30",
  validation_start: "2023-07-01",
  validation_end: "2024-06-28",
  sealed_test_start: "2024-07-01",
  sealed_test_end: "2024-12-31",
};

const DEFAULT_VALIDATION_CONFIG = {
  primary_horizon_sessions: 21,
  min_discovery_sessions: 20,
  min_validation_sessions: 20,
  min_sealed_test_sessions: 10,
  min_walk_forward_folds: 2,
  declared_hypothesis_family_size: 1,
  min_rank_ic: 0.02,
  max_turnover: 2.0,
  max_drawdown: 0.35,
};

const DEFAULT_BUDGET = {
  max_hypothesis_generation_calls: 3,
  max_hypotheses: 5,
  max_hypotheses_approved_for_translation: 3,
  max_formula_candidates_per_hypothesis: 2,
  max_total_formula_candidates: 8,
  max_formulas_reaching_evaluation: 6,
  max_revision_rounds_per_lineage: 2,
  max_total_revision_attempts: 4,
  max_llm_interactions: 40,
  max_failed_attempts: 8,
  max_validation_exposures_per_lineage: 2,
};

const DEFAULT_PAUSE_TRIGGERS = [
  "EVERY_HYPOTHESIS",
  "EVERY_FORMULA",
  "BEFORE_EACH_EXPERIMENT",
  "BEFORE_EACH_REVISION",
];

interface NewResearchFlowProps {
  readiness: MiningReadiness;
  onCreated: (sessionId: string) => void;
  onCancel: () => void;
}

export function NewResearchFlow({ readiness, onCreated, onCancel }: NewResearchFlowProps) {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [families, setFamilies] = useState<ResearchFamilyItem[]>([]);
  const [sessionName, setSessionName] = useState("");
  const [objective, setObjective] = useState("");
  const [economicIdea, setEconomicIdea] = useState("");
  const [familyId, setFamilyId] = useState("");
  const [createFamily, setCreateFamily] = useState(false);
  const [authReason, setAuthReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [draftSessionId, setDraftSessionId] = useState<string | null>(null);
  const [draftVersion, setDraftVersion] = useState(0);

  useEffect(() => {
    listResearchFamilies().then((r) => setFamilies(r.items)).catch(() => setFamilies([]));
  }, []);

  const providerId = readiness.data_provider === "historical_store" ? "historical_store" : "fixture";

  const submitDraft = async () => {
    setBusy(true);
    setError(null);
    try {
      let fid = familyId;
      if (createFamily || !fid) {
        const created = await createResearchFamily({
          research_objective: objective.slice(0, 200) || "Factor discovery research",
          intended_universe: "research",
          primary_horizon_sessions: DEFAULT_VALIDATION_CONFIG.primary_horizon_sessions,
          created_by: "quant-lab-ui",
        });
        fid = created.family_id;
      }
      const body = {
        research_family_id: fid,
        session_mode: "supervised",
        data_provider_id: providerId,
        actor: "quant-lab-ui",
        research_request: {
          research_objective: objective,
          session_name: sessionName || objective.slice(0, 80),
          economic_idea: economicIdea,
          candidate_count: 2,
          intended_universe: "research",
          primary_horizon_sessions: DEFAULT_VALIDATION_CONFIG.primary_horizon_sessions,
        },
        period_split: DEFAULT_PERIOD_SPLIT,
        validation_config: DEFAULT_VALIDATION_CONFIG,
        budget_policy: DEFAULT_BUDGET,
        pause_policy: { triggers: DEFAULT_PAUSE_TRIGGERS, pause_on_promising: true },
        auto_policy: {},
      };
      const created = await createMiningSession(body);
      setDraftSessionId(created.session_id);
      setDraftVersion(created.state_version ?? 0);
      setStep(7);
    } catch (e) {
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      setBusy(false);
    }
  };

  const submitAuthorize = async () => {
    if (!draftSessionId || !authReason.trim() || !confirmed) return;
    setBusy(true);
    setError(null);
    try {
      await authorizeMiningSession(draftSessionId, {
        actor: "quant-lab-ui",
        reason: authReason,
        expected_state_version: draftVersion,
      });
      onCreated(draftSessionId);
    } catch (e) {
      const parsed = parseFactorDiscoveryError(e);
      setError(`${parsed.message}. ${errorNextAction(parsed.code)}`);
    } finally {
      setBusy(false);
    }
  };

  const stepLabels = [
    "Objective",
    "Universe",
    "Data",
    "Family",
    "Budget",
    "Review policy",
    "Validation",
    "Authorize",
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1">
        {stepLabels.map((label, i) => (
          <button
            key={label}
            type="button"
            onClick={() => setStep(i)}
            className={clsx(
              "rounded px-2 py-0.5 text-xs",
              i === step ? "bg-zinc-700 text-zinc-50" : "bg-zinc-900 text-secondary"
            )}
          >
            {i + 1}. {label}
          </button>
        ))}
      </div>

      {error && <ErrorState message={error} />}

      {step === 0 && (
        <div className="space-y-2 text-sm">
          <label className="block">
            <span className="text-xs text-secondary">Session name</span>
            <input
              className="mt-0.5 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5"
              value={sessionName}
              onChange={(e) => setSessionName(e.target.value)}
              placeholder="e.g. Short-term momentum probe"
            />
          </label>
          <label className="block">
            <span className="text-xs text-secondary">Research objective *</span>
            <textarea
              required
              className="mt-0.5 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5"
              rows={3}
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="Describe the economic behavior to investigate (not an alpha guarantee)"
            />
          </label>
          <label className="block">
            <span className="text-xs text-secondary">Economic idea</span>
            <textarea
              className="mt-0.5 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5"
              rows={2}
              value={economicIdea}
              onChange={(e) => setEconomicIdea(e.target.value)}
              placeholder="Mechanism or pattern you want to test"
            />
          </label>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-2 text-xs text-secondary">
          <p>Universe: <strong className="text-foreground">research</strong> (backend-supported)</p>
          <p>Primary horizon: <strong className="text-foreground">{DEFAULT_VALIDATION_CONFIG.primary_horizon_sessions} sessions</strong> — immutable after authorization.</p>
          <p>Rebalance: monthly (default validation policy)</p>
          {!readiness.pit_fundamentals_ready && (
            <p className="text-amber-200">PIT fundamentals, sector/industry history, and market cap history are not available with the current provider.</p>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-secondary">
                <th className="py-1">Capability</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Adjusted prices", readiness.adjusted_prices_ready],
                ["PIT universe", readiness.pit_universe_ready],
                ["Fundamentals", readiness.pit_fundamentals_ready],
                ["Sector history", readiness.sector_history_ready],
                ["Market cap history", readiness.market_cap_history_ready],
              ].map(([label, ok]) => (
                <tr key={String(label)} className="border-t border-zinc-800">
                  <td className="py-1">{label}</td>
                  <td className={ok ? "text-emerald-300" : "text-red-300"}>{ok ? "Available" : "Unavailable"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-2 text-sm">
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={createFamily} onChange={(e) => setCreateFamily(e.target.checked)} />
            Create new research family
          </label>
          {!createFamily && (
            <select
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
              value={familyId}
              onChange={(e) => setFamilyId(e.target.value)}
            >
              <option value="">Select family…</option>
              {families.map((f) => (
                <option key={f.family_id} value={f.family_id} disabled={f.closed}>
                  {f.research_objective.slice(0, 60)} ({f.formula_attempt_count} attempts)
                </option>
              ))}
            </select>
          )}
          <p className="text-xs text-secondary">Family cannot change after authorization. Creating a new family only to reset attempt counts is not allowed.</p>
        </div>
      )}

      {step === 4 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.entries(DEFAULT_BUDGET).map(([k, v]) => (
            <MetricTile key={k} label={k.replaceAll("_", " ")} value={v} variant="compact" />
          ))}
        </div>
      )}

      {step === 5 && (
        <div className="text-xs text-secondary space-y-1">
          <p>Mode: <strong className="text-foreground">Supervised</strong></p>
          <p>Required pauses: hypothesis, formula, experiment launch, revision approval.</p>
          <p className="text-amber-200">Bounded auto: not ready — not selectable.</p>
        </div>
      )}

      {step === 6 && (
        <div className="text-xs text-secondary space-y-1">
          <p>Discovery / validation / sealed periods use project defaults.</p>
          <p className="text-amber-200">Sealed-test results will not be opened by this workspace.</p>
          <p>Min Rank IC: {DEFAULT_VALIDATION_CONFIG.min_rank_ic} · Walk-forward folds: {DEFAULT_VALIDATION_CONFIG.min_walk_forward_folds}</p>
        </div>
      )}

      {step === 7 && (
        <div className="space-y-2 text-sm">
          <p className="text-xs text-secondary">Review immutable summary before authorization.</p>
          <ul className="list-inside list-disc text-xs text-secondary">
            <li>{objective || "—"}</li>
            <li>Provider: {providerId}</li>
            <li>Horizon: {DEFAULT_VALIDATION_CONFIG.primary_horizon_sessions} sessions</li>
          </ul>
          <label className="block">
            <span className="text-xs text-secondary">Authorization reason *</span>
            <textarea
              className="mt-0.5 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
              rows={2}
              value={authReason}
              onChange={(e) => setAuthReason(e.target.value)}
            />
          </label>
          <label className="flex items-start gap-2 text-xs">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
            <span>I confirm this is controlled research — not investment approval or production deployment.</span>
          </label>
          {draftSessionId && (
            <p className="text-xs text-emerald-300">Draft created: {draftSessionId}</p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-2">
        <button type="button" className="btn-secondary px-3 py-1.5 text-sm" onClick={onCancel}>
          Cancel
        </button>
        {step > 0 && (
          <button type="button" className="btn-secondary px-3 py-1.5 text-sm" onClick={() => setStep(step - 1)}>
            Back
          </button>
        )}
        {step < 6 && (
          <button
            type="button"
            className="btn-primary px-3 py-1.5 text-sm"
            disabled={step === 0 && !objective.trim()}
            onClick={() => setStep(step + 1)}
          >
            Next
          </button>
        )}
        {step === 6 && !draftSessionId && (
          <button type="button" className="btn-primary px-3 py-1.5 text-sm" disabled={busy || !objective.trim()} onClick={submitDraft}>
            {busy ? "Creating…" : "Create draft"}
          </button>
        )}
        {step === 7 && (
          <button
            type="button"
            className="btn-primary px-3 py-1.5 text-sm"
            disabled={busy || !draftSessionId || !authReason.trim() || !confirmed}
            onClick={submitAuthorize}
          >
            {busy ? "Authorizing…" : "Authorize session"}
          </button>
        )}
      </div>
    </div>
  );
}
