"use client";

import { approveHypothesis, rejectHypothesis } from "@/lib/api/factorDiscovery/client";
import { parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import type { HypothesisCandidateDetail } from "@/lib/api/factorDiscovery/types";
import { ReviewConfirmDialog } from "./ReviewConfirmDialog";
import { useState } from "react";

const CRITIQUE_KEYS = [
  "economic_plausibility_concerns",
  "data_availability_concerns",
  "pit_concerns",
  "survivorship_concerns",
  "redundancy_concerns",
  "turnover_concerns",
  "horizon_mismatch",
  "regime_dependence",
  "leakage_risks",
  "critic_recommendation",
  "human_review_questions",
] as const;

export function HypothesisReviewCard({
  detail,
  onRefresh,
  onViewInteraction,
}: {
  detail: HypothesisCandidateDetail;
  onRefresh: () => void;
  onViewInteraction?: (interactionId: string) => void;
}) {
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);

  const critique = detail.critique?.summary as Record<string, unknown> | undefined;

  async function submit(action: "approve" | "reject") {
    if (!detail.session_id || detail.state_version == null) return;
    setLoading(true);
    setConflict(null);
    try {
      const payload = {
        candidate_id: detail.candidate_id,
        expected_state_version: detail.state_version,
        actor: "human_reviewer",
        reason: reason.trim(),
      };
      if (action === "approve") await approveHypothesis(detail.session_id, detail.candidate_id, payload);
      else await rejectHypothesis(detail.session_id, detail.candidate_id, payload);
      setDialog(null);
      onRefresh();
    } catch (e) {
      const err = parseFactorDiscoveryError(e);
      if (err.code === "STATE_VERSION_CONFLICT") {
        setConflict(err.message);
        onRefresh();
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <article className="space-y-4 rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold">{detail.candidate_name ?? detail.candidate_id}</h3>
          <p className="text-sm text-zinc-500">Review status: {detail.review_status}</p>
        </div>
        <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
          Support: {detail.deterministic_support_status ?? "unknown"}
        </span>
      </header>

      <Section title="Economic rationale" body={detail.economic_rationale} />
      <Section title="Expected mechanism" body={detail.expected_mechanism} />
      <MetaGrid
        items={[
          ["Direction", detail.expected_direction],
          ["Universe", detail.intended_universe],
          ["Holding period", detail.holding_period_sessions?.toString()],
          ["Rebalance", detail.rebalance_frequency],
          ["Turnover", detail.expected_turnover],
          ["Benchmark overlap", detail.benchmark_overlap],
        ]}
      />
      <TagList title="Required data classes" items={detail.required_data_classes} />
      <TagList title="Proposed fields" items={detail.proposed_fields} />
      <TagList title="Risks" items={detail.known_risks} />
      <TagList title="Failure conditions" items={detail.expected_failure_conditions} />
      <TagList title="Assumptions" items={detail.assumptions} />

      {critique ? (
        <section aria-labelledby="hypothesis-critique">
          <h4 id="hypothesis-critique" className="text-sm font-semibold">
            LLM critique (research opinion)
          </h4>
          <ul className="mt-2 space-y-2 text-sm">
            {CRITIQUE_KEYS.map((key) => {
              const val = critique[key];
              if (!val) return null;
              return (
                <li key={key} className="rounded border border-violet-200/60 bg-violet-50/50 p-2 dark:border-violet-900/40 dark:bg-violet-950/20">
                  <span className="font-medium capitalize">{key.replace(/_/g, " ")}: </span>
                  {Array.isArray(val) ? val.join("; ") : String(val)}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {detail.allowed_actions.can_approve ? (
          <button
            type="button"
            className="rounded bg-emerald-700 px-3 py-1.5 text-sm text-white"
            onClick={() => setDialog("approve")}
          >
            Approve for formula translation
          </button>
        ) : null}
        {detail.allowed_actions.can_reject ? (
          <button
            type="button"
            className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 dark:border-red-800 dark:text-red-300"
            onClick={() => setDialog("reject")}
          >
            Reject
          </button>
        ) : null}
        {detail.critique?.interaction_id && onViewInteraction ? (
          <button
            type="button"
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600"
            onClick={() => onViewInteraction(detail.critique!.interaction_id)}
          >
            View LLM interaction
          </button>
        ) : null}
        <button
          type="button"
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600"
          onClick={() => navigator.clipboard.writeText(detail.candidate_id)}
        >
          Copy candidate ID
        </button>
      </div>

      <p className="text-xs text-zinc-500">
        Approving permits formula translation. It does not approve the factor or launch an experiment.
      </p>

      <ReviewConfirmDialog
        open={dialog === "approve"}
        title="Approve hypothesis"
        description="Approving permits formula translation. It does not approve the factor or launch an experiment."
        confirmLabel="Approve hypothesis"
        reason={reason}
        onReasonChange={setReason}
        onConfirm={() => submit("approve")}
        onCancel={() => setDialog(null)}
        loading={loading}
        conflictMessage={conflict}
      />
      <ReviewConfirmDialog
        open={dialog === "reject"}
        title="Reject hypothesis"
        description="Rejecting removes this hypothesis from the translation queue."
        confirmLabel="Reject hypothesis"
        reason={reason}
        onReasonChange={setReason}
        onConfirm={() => submit("reject")}
        onCancel={() => setDialog(null)}
        loading={loading}
        conflictMessage={conflict}
      />
    </article>
  );
}

function Section({ title, body }: { title: string; body?: string }) {
  if (!body) return null;
  return (
    <section>
      <h4 className="text-sm font-semibold">{title}</h4>
      <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">{body}</p>
    </section>
  );
}

function MetaGrid({ items }: { items: [string, string | undefined][] }) {
  return (
    <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
      {items.map(([k, v]) =>
        v ? (
          <div key={k}>
            <dt className="text-zinc-500">{k}</dt>
            <dd>{v}</dd>
          </div>
        ) : null
      )}
    </dl>
  );
}

function TagList({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <section>
      <h4 className="text-sm font-semibold">{title}</h4>
      <ul className="mt-1 flex flex-wrap gap-1">
        {items.map((item) => (
          <li key={item} className="rounded bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
            {item}
          </li>
        ))}
      </ul>
    </section>
  );
}
