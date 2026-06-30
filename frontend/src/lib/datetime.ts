/** Parse Robinhood ledger dates (M/D/YYYY, YYYY-MM-DD, or ISO). Returns ms UTC; NaN if unknown. */
export function parseLedgerActivityDate(value: string | null | undefined): number {
  if (!value?.trim()) return NaN;
  const s = value.trim();
  if (s.includes("T")) {
    const t = parseApiDate(s).getTime();
    if (!Number.isNaN(t)) return t;
  }
  const ymd = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (ymd) return Date.UTC(Number(ymd[1]), Number(ymd[2]) - 1, Number(ymd[3]));
  const mdy = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (mdy) return Date.UTC(Number(mdy[3]), Number(mdy[1]) - 1, Number(mdy[2]));
  const t = new Date(s).getTime();
  return Number.isNaN(t) ? NaN : t;
}

type LedgerSortable = {
  activity_date?: string | null;
  process_date?: string | null;
  executed_at?: string | null;
  id?: number;
};

/** Newest activity first; tie-break by id descending. */
export function compareLedgerRowsDesc(a: LedgerSortable, b: LedgerSortable): number {
  const ts = (row: LedgerSortable) => {
    for (const field of [row.executed_at, row.activity_date, row.process_date]) {
      const t = parseLedgerActivityDate(field);
      if (!Number.isNaN(t)) return t;
    }
    return NaN;
  };
  const aT = ts(a);
  const bT = ts(b);
  if (!Number.isNaN(aT) && !Number.isNaN(bT) && aT !== bT) return bT - aT;
  if (!Number.isNaN(aT) && Number.isNaN(bT)) return -1;
  if (Number.isNaN(aT) && !Number.isNaN(bT)) return 1;
  return (b.id ?? 0) - (a.id ?? 0);
}

/**
 * API timestamps are UTC with a Z suffix (or legacy naive UTC → treat as Z).
 * datetime-local inputs use the browser's local timezone.
 */
export function parseApiDate(value: string | null | undefined): Date {
  if (!value) return new Date(NaN);
  const s = value.trim();
  if (!s) return new Date(NaN);
  if (/Z$|[+-]\d{2}:\d{2}$/.test(s)) {
    return new Date(s);
  }
  // Backend legacy: naive ISO datetime is UTC
  if (s.includes("T")) {
    return new Date(`${s}Z`);
  }
  return new Date(s);
}

export function formatDateTime(
  value: string | null | undefined,
  options?: Intl.DateTimeFormatOptions
): string {
  if (!value) return "—";
  const d = parseApiDate(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    ...options,
  });
}

/** Value for `<input type="datetime-local" />` in local time. */
export function toDatetimeLocalValue(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const h = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d}T${h}:${min}`;
}

/** Parse datetime-local string as local wall time. */
export function fromDatetimeLocalValue(value: string): Date {
  return new Date(value);
}

/** API UTC ISO → datetime-local for editing existing trades. */
export function apiDateToDatetimeLocal(iso: string | null | undefined): string {
  if (!iso) return toDatetimeLocalValue();
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return toDatetimeLocalValue();
  return toDatetimeLocalValue(d);
}
