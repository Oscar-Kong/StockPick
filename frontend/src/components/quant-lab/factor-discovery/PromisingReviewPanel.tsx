"use client";

import { RuleTable, type RuleRow } from "./RuleTable";

export function PromisingReviewPanel({
  policy,
  artifactId,
  sessionId,
}: {
  policy: Record<string, unknown> | null;
  artifactId?: string | null;
  sessionId?: string | null;
}) {
  const overall = policy?.overall_result ?? policy?.overall_promising_result ?? "unknown";
  const rules: RuleRow[] = Array.isArray(policy?.rules)
    ? (policy!.rules as Record<string, unknown>[]).map((row) => ({
        category: "Promising",
        rule: String(row.rule ?? row.name ?? ""),
        actual: row.actual != null ? String(row.actual) : null,
        required: row.threshold != null ? String(row.threshold) : null,
        status: String(row.status ?? row.result ?? ""),
        reason: row.reason != null ? String(row.reason) : null,
        evidence: row.evidence_path != null ? String(row.evidence_path) : null,
      }))
    : [];

  return (
    <section className="space-y-3 rounded-lg border border-emerald-900/40 bg-emerald-950/15 p-4">
      <header>
        <h3 className="text-base font-semibold text-emerald-100">Promising for human review</h3>
        <p className="text-sm text-emerald-100/80">Overall: {String(overall)}</p>
      </header>

      <div className="space-y-1 text-xs text-emerald-100/90">
        <p>This is promising research evidence, not investment approval.</p>
        <p>The sealed test remains unopened.</p>
        <p>No lifecycle promotion has occurred.</p>
      </div>

      {rules.length ? <RuleTable rows={rules} caption="Promising policy rules" /> : null}

      <dl className="grid grid-cols-2 gap-2 text-xs text-emerald-100/80">
        {artifactId ? (
          <div>
            <dt>Artifact</dt>
            <dd className="font-mono">{artifactId}</dd>
          </div>
        ) : null}
        {sessionId ? (
          <div>
            <dt>Session</dt>
            <dd className="font-mono">{sessionId}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
