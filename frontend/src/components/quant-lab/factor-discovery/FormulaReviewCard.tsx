"use client";

import { approveFormula, rejectFormula } from "@/lib/api/factorDiscovery/client";
import { parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import type { FormulaCandidateDetail } from "@/lib/api/factorDiscovery/types";
import { AstTreeView } from "./AstTreeView";
import { ReviewConfirmDialog } from "./ReviewConfirmDialog";
import { useState } from "react";

export function FormulaReviewCard({
  detail,
  onRefresh,
  onViewInteraction: _onViewInteraction,
}: {
  detail: FormulaCandidateDetail;
  onRefresh: () => void;
  onViewInteraction?: (interactionId: string) => void;
}) {
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);

  const review = detail.formula_review?.summary as Record<string, unknown> | undefined;

  async function submit(action: "approve" | "reject") {
    if (!detail.session_id || detail.state_version == null) return;
    setLoading(true);
    setConflict(null);
    try {
      const payload = {
        expected_state_version: detail.state_version,
        actor: "human_reviewer",
        reason: reason.trim(),
      };
      if (action === "approve") await approveFormula(detail.session_id, detail.candidate_id, payload);
      else await rejectFormula(detail.session_id, detail.candidate_id, payload);
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
      <header>
        <h3 className="text-base font-semibold">{detail.proposed_factor_name ?? detail.candidate_id}</h3>
        <p className="text-sm text-zinc-500">
          Review: {detail.review_status} · Compile: {detail.compile_status ?? "unknown"}
          {detail.duplicate_status ? ` · Duplicate: ${detail.duplicate_status}` : ""}
        </p>
      </header>

      <section>
        <h4 className="text-sm font-semibold">Canonical DSL</h4>
        <pre className="mt-1 max-h-48 overflow-auto rounded bg-zinc-950 p-3 font-mono text-xs text-zinc-100">
          {detail.canonical_dsl ?? "—"}
        </pre>
        {detail.original_llm_dsl && detail.original_llm_dsl !== detail.canonical_dsl ? (
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer text-zinc-500">Original LLM DSL</summary>
            <pre className="mt-1 overflow-auto rounded bg-zinc-900 p-2 font-mono">{detail.original_llm_dsl}</pre>
          </details>
        ) : null}
      </section>

      <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-zinc-500">Formula hash</dt>
          <dd className="truncate font-mono text-xs">{detail.formula_hash ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Direction</dt>
          <dd>{detail.expected_direction ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Nodes / depth</dt>
          <dd>
            {detail.ast_node_count ?? "—"} / {detail.ast_depth ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500">Operators</dt>
          <dd>{detail.operators_used?.join(", ") ?? "—"}</dd>
        </div>
      </dl>

      {detail.compiler_required_fields?.length ? (
        <section>
          <h4 className="text-sm font-semibold">Required fields</h4>
          <p className="text-sm">{detail.compiler_required_fields.join(", ")}</p>
        </section>
      ) : null}

      {detail.compiler_warnings?.length ? (
        <section aria-labelledby="compiler-warnings">
          <h4 id="compiler-warnings" className="text-sm font-semibold text-amber-700 dark:text-amber-300">
            Compiler warnings (deterministic)
          </h4>
          <ul className="mt-1 list-inside list-disc text-sm">
            {detail.compiler_warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <AstTreeView ast={detail.canonical_ast} />

      {review ? (
        <section aria-labelledby="formula-review">
          <h4 id="formula-review" className="text-sm font-semibold">
            Formula review (LLM opinion)
          </h4>
          <ul className="mt-2 space-y-1 text-sm">
            {Object.entries(review).map(([k, v]) =>
              v ? (
                <li key={k}>
                  <span className="font-medium capitalize">{k.replace(/_/g, " ")}: </span>
                  {Array.isArray(v) ? v.join("; ") : String(v)}
                </li>
              ) : null
            )}
          </ul>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {detail.allowed_actions.can_approve ? (
          <button type="button" className="rounded bg-emerald-700 px-3 py-1.5 text-sm text-white" onClick={() => setDialog("approve")}>
            Approve formula
          </button>
        ) : null}
        {detail.allowed_actions.can_reject ? (
          <button
            type="button"
            className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 dark:border-red-800 dark:text-red-300"
            onClick={() => setDialog("reject")}
          >
            Reject formula
          </button>
        ) : null}
      </div>

      <p className="text-xs text-zinc-500">
        Approving creates or permits an immutable draft definition. It does not validate the factor or authorize production use.
      </p>

      <ReviewConfirmDialog
        open={dialog === "approve"}
        title="Approve formula"
        description="Approving creates or permits an immutable draft definition. It does not validate the factor or authorize production use."
        confirmLabel="Approve formula"
        reason={reason}
        onReasonChange={setReason}
        onConfirm={() => submit("approve")}
        onCancel={() => setDialog(null)}
        loading={loading}
        conflictMessage={conflict}
      />
      <ReviewConfirmDialog
        open={dialog === "reject"}
        title="Reject formula"
        description="Rejecting removes this formula from the approval queue."
        confirmLabel="Reject formula"
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
