"use client";

export interface RuleRow {
  category?: string;
  rule: string;
  actual?: string | number | null;
  required?: string | number | null;
  status: string;
  evidence?: string | null;
  reason?: string | null;
}

export function RuleTable({
  rows,
  filterFailed = false,
  caption,
}: {
  rows: RuleRow[];
  filterFailed?: boolean;
  caption?: string;
}) {
  const visible = filterFailed
    ? rows.filter((r) => ["FAIL", "FAILED", "fail", "failed"].includes(String(r.status)))
    : rows;

  if (!visible.length) {
    return <p className="text-sm text-zinc-500">No rules to display.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm" aria-label={caption ?? "Rule evaluation table"}>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr className="border-b border-zinc-200 dark:border-zinc-700">
            <th scope="col" className="py-2 pr-3 font-medium">
              Category
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Rule
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Actual
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Required
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row, i) => (
            <tr key={`${row.rule}-${i}`} className="border-b border-zinc-100 dark:border-zinc-800">
              <td className="py-2 pr-3 align-top text-zinc-600 dark:text-zinc-400">{row.category ?? "—"}</td>
              <td className="py-2 pr-3 align-top">{row.rule}</td>
              <td className="py-2 pr-3 align-top font-mono text-xs">{row.actual ?? "—"}</td>
              <td className="py-2 pr-3 align-top font-mono text-xs">{row.required ?? "—"}</td>
              <td className="py-2 pr-3 align-top">
                <RuleStatusChip status={row.status} />
                {row.reason ? <p className="mt-1 text-xs text-zinc-500">{row.reason}</p> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RuleStatusChip({ status }: { status: string }) {
  const normalized = status.toUpperCase();
  const tone =
    normalized === "PASS" || normalized === "PASSED"
      ? "text-emerald-700 dark:text-emerald-300"
      : normalized === "FAIL" || normalized === "FAILED"
        ? "text-red-700 dark:text-red-300"
        : normalized === "INCONCLUSIVE"
          ? "text-amber-700 dark:text-amber-300"
          : "text-zinc-600 dark:text-zinc-400";
  return <span className={`text-xs font-medium ${tone}`}>{status}</span>;
}
