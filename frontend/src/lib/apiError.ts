/** Parse FastAPI / fetch error bodies into a human-readable message. */
import type { ApiStructuredError } from "./types";

export function parseApiError(error: unknown, fallback = "Request failed"): string {
  if (!(error instanceof Error)) return fallback;
  const raw = error.message.trim();
  if (!raw) return fallback;

  try {
    const parsed = JSON.parse(raw) as {
      detail?: string | ApiStructuredError | Array<string | { msg?: string }> | Record<string, unknown>;
    };
    const { detail } = parsed;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const structured = detail as ApiStructuredError;
      if (typeof structured.message === "string") {
        const suffix = structured.request_id ? ` (${structured.request_id})` : "";
        return `${structured.message}${suffix}`;
      }
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (typeof item === "string" ? item : item.msg ?? JSON.stringify(item)))
        .join("; ");
    }
    if (detail && typeof detail === "object") {
      return JSON.stringify(detail);
    }
  } catch {
    // Not JSON — use raw text below.
  }

  return raw;
}

/** True when the backend feature flag is off (503) or similar. */
export function isFeatureDisabledError(message: string): boolean {
  const m = message.toLowerCase();
  return (
    m.includes("503") ||
    m.includes("score_engine") ||
    m.includes("trade_feedback") ||
    m.includes("not enabled") ||
    m.includes("disabled") ||
    m.includes("demo_action_disabled")
  );
}
