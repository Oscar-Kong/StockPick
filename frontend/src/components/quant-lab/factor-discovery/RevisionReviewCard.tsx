"use client";

import { approveRevision, rejectRevision } from "@/lib/api/factorDiscovery/client";
import { parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import type { RevisionCandidateDetail } from "@/lib/api/factorDiscovery/types";
import { ReviewConfirmDialog } from "./ReviewConfirmDialog";
import { RuleTable, type RuleRow } from "./RuleTable";
import { useMemo, useState } from "react";

export function RevisionReviewCard({
  detail,
  onRefresh,
}: {
  detail: RevisionCandidateDetail;
  onRefresh: () => void;
}) {
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);

  const policyRows = useMemo((): RuleRow[] => {
    const rules = detail.revision_policy_rules;
    if (!Array.isArray(rules)) return [];
    return rules.map((r) => {
      const row = r as Record<string, unknown>;
      return {
        category: "Revision policy",
        rule: String(row.rule ?? row.name ?? "rule"),
        actual: row.actual != null ? String(row.actual) : null,
        required: row.allowed != null ? String(row.allowed) : row.threshold != null ? String(row.threshold) : null,
        status: String(row.status ?? row.result ?? "unknown"),
        reason: row.reason != null ? String(row.reason) : null,
      };
    });
  }, [detail.revision_policy_rules]);

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
      if (action === "approve") await approveRevision(detail.session_id, detail.candidate_id, payload);
      else await rejectRevision(detail.session_id, detail.candidate_id, payload);
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
        <h3 className="text-base font-semibold">Revision {detail.candidate_id}</h3>
        <p className="text-sm text-zinc-500">
          Review: {detail.review_status} · Policy: {detail.policy_result ?? "—"}
        </p>
        {(detail.exact_duplicate || detail.near_duplicate) && (
          <p className="mt-1 text-sm text-amber-700 dark:text-amber-300" role="alert">
            {detail.exact_duplicate ? "Exact duplicate detected." : "Near duplicate detected."}
          </p>
        )}
      </header>

      {detail.revision_rationale ? (
        <section>
          <h4 className="text-sm font-semibold">Revision rationale</h4>
          <p className="text-sm">{detail.revision_rationale}</p>
        </section>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <DslBlock title="Parent canonical DSL" dsl={detail.parent_canonical_dsl} />
        <DslBlock title="Proposed canonical DSL" dsl={detail.proposed_canonical_dsl} />
      </div>

      <section aria-labelledby="semantic-diff">
        <h4 id="semantic-diff" className="text-sm font-semibold">
          Semantic changes
        </h4>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          <Chip label="Fields +" items={detail.fields_added} />
          <Chip label="Fields −" items={detail.fields_removed} />
          <MetricChip label="Node Δ" value={detail.node_count_delta} />
          <MetricChip label="Depth Δ" value={detail.depth_delta} />
          <MetricChip label="Similarity" value={detail.structural_similarity} />
        </div>
      </section>

      {policyRows.length ? (
        <section>
          <h4 className="text-sm font-semibold">Revision policy</h4>
          <RuleTable rows={policyRows} caption="Revision policy rules" />
        </section>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {detail.allowed_actions.can_approve ? (
          <button type="button" className="rounded bg-emerald-700 px-3 py-1.5 text-sm text-white" onClick={() => setDialog("approve")}>
            Approve revision
          </button>
        ) : null}
        {detail.allowed_actions.can_reject ? (
          <button
            type="button"
            className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 dark:border-red-800 dark:text-red-300"
            onClick={() => setDialog("reject")}
          >
            Reject revision
          </button>
        ) : null}
      </div>

      <p className="text-xs text-zinc-500">
        Approving creates a new immutable version. The previous version and its research results remain unchanged.
      </p>

      <ReviewConfirmDialog
        open={dialog === "approve"}
        title="Approve revision"
        description="Approving creates a new immutable version. The previous version and its research results remain unchanged."
        confirmLabel="Approve revision"
        reason={reason}
        onReasonChange={setReason}
        onConfirm={() => submit("approve")}
        onCancel={() => setDialog(null)}
        loading={loading}
        conflictMessage={conflict}
      />
      <ReviewConfirmDialog
        open={dialog === "reject"}
        title="Reject revision"
        description="Rejecting discards this revision proposal."
        confirmLabel="Reject revision"
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

function DslBlock({ title, dsl }: { title: string; dsl?: string }) {
  return (
    <section>
      <h4 className="text-sm font-semibold">{title}</h4>
      <pre className="mt-1 max-h-40 overflow-auto rounded bg-zinc-950 p-2 font-mono text-xs text-zinc-100">{dsl ?? "—"}</pre>
    </section>
  );
}

function Chip({ label, items }: { label: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <span className="rounded bg-zinc-100 px-2 py-1 dark:bg-zinc-800">
      {label}: {items.join(", ")}
    </span>
  );
}

function MetricChip({ label, value }: { label: string; value?: string | number | null }) {
  if (value == null || value === "") return null;
  return (
    <span className="rounded bg-zinc-100 px-2 py-1 dark:bg-zinc-800">
      {label}: {value}
    </span>
  );
}
