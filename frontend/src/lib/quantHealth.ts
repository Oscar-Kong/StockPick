import type { QuantHealthSection, QuantHealthSeverity } from "./types";

export function severityFromSections(sections: QuantHealthSection[]): QuantHealthSeverity {
  if (sections.some((s) => s.severity === "error")) return "error";
  if (sections.some((s) => s.severity === "warning")) return "warning";
  return "ok";
}

export function isStaleTimestamp(iso: string | null | undefined, maxAgeMs: number): boolean {
  if (!iso) return true;
  const age = Date.now() - new Date(iso).getTime();
  return Number.isNaN(age) || age > maxAgeMs;
}
