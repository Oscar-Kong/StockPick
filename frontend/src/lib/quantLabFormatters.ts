export const PAIRS_MAX_SYMBOLS = 20;

export function parseSymbolList(input: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of input.split(/[\s,]+/)) {
    const sym = raw.trim().toUpperCase();
    if (!sym || seen.has(sym)) continue;
    seen.add(sym);
    out.push(sym);
  }
  return out;
}

export function defaultWalkForwardDates(): { start_date: string; end_date: string } {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 2);
  return {
    start_date: start.toISOString().slice(0, 10),
    end_date: end.toISOString().slice(0, 10),
  };
}

export function validateWalkForwardDates(startDate: string, endDate: string): string | null {
  const start = new Date(startDate);
  const end = new Date(endDate);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return "invalid_date";
  }
  if (start >= end) {
    return "start_after_end";
  }
  return null;
}

export function formatWalkForwardHorizonStats(stats: unknown): string {
  if (stats == null) return "—";
  if (typeof stats !== "object") return String(stats);
  const s = stats as Record<string, unknown>;
  const parts: string[] = [];
  if (typeof s.periods === "number") parts.push(`${s.periods} periods`);
  if (typeof s.sufficient === "boolean") {
    parts.push(s.sufficient ? "sufficient data" : "insufficient data");
  }
  if (typeof s.mean_ic === "number" && Number.isFinite(s.mean_ic)) {
    parts.push(`mean IC ${s.mean_ic.toFixed(3)}`);
  }
  if (typeof s.hit_rate === "number" && Number.isFinite(s.hit_rate)) {
    parts.push(`hit ${(s.hit_rate * 100).toFixed(0)}%`);
  }
  return parts.length > 0 ? parts.join(" · ") : "—";
}
