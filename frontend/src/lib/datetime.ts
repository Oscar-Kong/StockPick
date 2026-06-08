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
