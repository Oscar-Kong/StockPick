"use client";

import type { ValidationResultDetail } from "@/lib/api/factorDiscovery/types";
import { IntegrityBadge } from "./IntegrityBadge";
import { RuleTable, type RuleRow } from "./RuleTable";
import { useMemo, useState } from "react";

const SECTIONS = [
  "Overview",
  "Signal",
  "Quantiles",
  "Cost & Turnover",
  "Walk-Forward",
  "Robustness",
  "Redundancy",
  "Statistics",
  "Multiple Testing",
  "Acceptance Rules",
  "Limitations",
] as const;

type Section = (typeof SECTIONS)[number];

export function ValidationResultPanel({ result }: { result: ValidationResultDetail }) {
  const [section, setSection] = useState<Section>("Overview");
  const trust = result.trust_metrics && result.integrity.integrity_status === "VERIFIED";

  const acceptanceRows = useMemo(() => rowsFromAcceptance(result.acceptance), [result.acceptance]);
  const promisingRows = useMemo(() => rowsFromPromising(result.promising_policy), [result.promising_policy]);

  const overview = result.overview as Record<string, unknown>;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold">
            {String(overview.factor_id ?? result.artifact_id)} v{String(overview.version ?? "—")}
          </h3>
          <p className="text-sm text-zinc-500">
            {String(overview.validation_status_label ?? overview.acceptance_status ?? "Research result")}
          </p>
        </div>
        <IntegrityBadge
          status={result.integrity.integrity_status}
          errorSummary={result.integrity.integrity_error_summary}
        />
      </header>

      {!trust ? (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200" role="alert">
          Metrics are not trusted until artifact integrity is verified.
          {result.integrity.integrity_error_summary ? ` ${result.integrity.integrity_error_summary}` : ""}
        </div>
      ) : null}

      <p className="text-xs text-zinc-500">Sealed test remains unopened. Research simulation — not live portfolio performance.</p>

      <nav className="flex flex-wrap gap-1" aria-label="Validation result sections">
        {SECTIONS.map((s) => (
          <button
            key={s}
            type="button"
            className={`rounded px-2 py-1 text-xs ${section === s ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900" : "bg-zinc-100 dark:bg-zinc-800"}`}
            onClick={() => setSection(s)}
          >
            {s}
          </button>
        ))}
      </nav>

      {section === "Overview" && <MetricGrid data={overview} trust={trust} />}
      {section === "Signal" && <MetricGrid data={result.signal} trust={trust} />}
      {section === "Quantiles" && <MetricGrid data={result.quantiles} trust={trust} />}
      {section === "Cost & Turnover" && <MetricGrid data={result.portfolio} trust={trust} />}
      {section === "Walk-Forward" && <JsonSection data={result.walk_forward} trust={trust} />}
      {section === "Robustness" && <JsonSection data={result.robustness} trust={trust} />}
      {section === "Redundancy" && <JsonSection data={result.redundancy} trust={trust} />}
      {section === "Statistics" && <MetricGrid data={result.statistical} trust={trust} />}
      {section === "Multiple Testing" && <MetricGrid data={result.multiple_testing} trust={trust} />}
      {section === "Acceptance Rules" && (
        <RuleTable rows={acceptanceRows} caption="Acceptance rules" filterFailed={false} />
      )}
      {section === "Limitations" && (
        <ul className="list-inside list-disc text-sm text-zinc-600 dark:text-zinc-400">
          {result.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}

      {promisingRows.length ? (
        <section>
          <h4 className="text-sm font-semibold">Promising policy rules</h4>
          <RuleTable rows={promisingRows} caption="Promising policy" />
        </section>
      ) : null}
    </div>
  );
}

function MetricGrid({ data, trust }: { data: Record<string, unknown>; trust: boolean }) {
  const entries = Object.entries(data).filter(([, v]) => v != null && typeof v !== "object");
  if (!entries.length) return <p className="text-sm text-zinc-500">No metrics in this section.</p>;
  return (
    <dl className={`grid grid-cols-2 gap-2 text-sm sm:grid-cols-3 ${trust ? "" : "opacity-60"}`}>
      {entries.map(([k, v]) => (
        <div key={k}>
          <dt className="text-zinc-500">{k.replace(/_/g, " ")}</dt>
          <dd className="font-medium">{String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function JsonSection({ data, trust }: { data: Record<string, unknown>; trust: boolean }) {
  return (
    <pre className={`overflow-auto rounded bg-zinc-950 p-3 text-xs text-zinc-100 ${trust ? "" : "opacity-60"}`}>
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function rowsFromAcceptance(acceptance: Record<string, unknown>): RuleRow[] {
  const rules = acceptance.rules;
  if (!Array.isArray(rules)) return [];
  return rules.map((r) => {
    const row = r as Record<string, unknown>;
    return {
      category: String(row.category ?? ""),
      rule: String(row.rule ?? row.name ?? ""),
      actual: row.actual != null ? String(row.actual) : null,
      required: row.threshold != null ? String(row.threshold) : row.required != null ? String(row.required) : null,
      status: String(row.status ?? ""),
      reason: row.reason != null ? String(row.reason) : null,
      evidence: row.evidence_path != null ? String(row.evidence_path) : null,
    };
  });
}

function rowsFromPromising(policy: Record<string, unknown> | null): RuleRow[] {
  if (!policy) return [];
  const rules = policy.rules;
  if (!Array.isArray(rules)) return [];
  return rules.map((r) => {
    const row = r as Record<string, unknown>;
    return {
      category: "Promising",
      rule: String(row.rule ?? row.name ?? ""),
      actual: row.actual != null ? String(row.actual) : null,
      required: row.threshold != null ? String(row.threshold) : null,
      status: String(row.status ?? row.result ?? ""),
      reason: row.reason != null ? String(row.reason) : null,
      evidence: row.evidence_path != null ? String(row.evidence_path) : null,
    };
  });
}
