/** Parse Factor Discovery API errors for UI display. */

export interface FactorDiscoveryApiError {
  code: string;
  message: string;
  state_version?: number;
}

export function parseFactorDiscoveryError(err: unknown): FactorDiscoveryApiError {
  const fallback = { code: "UNKNOWN", message: err instanceof Error ? err.message : "Request failed" };
  if (!(err instanceof Error)) return fallback;
  try {
    const raw = err.message;
    const jsonStart = raw.indexOf("{");
    if (jsonStart >= 0) {
      const parsed = JSON.parse(raw.slice(jsonStart)) as { detail?: FactorDiscoveryApiError | string };
      if (typeof parsed.detail === "object" && parsed.detail?.code) return parsed.detail;
      if (typeof parsed.detail === "string") return { code: "API_ERROR", message: parsed.detail };
    }
  } catch {
    /* ignore */
  }
  if (err.message.includes("503")) return { code: "FEATURE_DISABLED", message: "Factor Discovery is disabled on the backend" };
  if (err.message.includes("409")) return { code: "STATE_VERSION_CONFLICT", message: "Session state changed — refresh and retry" };
  return fallback;
}

export function errorNextAction(code: string): string {
  switch (code) {
    case "STATE_VERSION_CONFLICT":
      return "Refresh the session and resubmit your action.";
    case "FEATURE_DISABLED":
    case "FACTOR_DISCOVERY_LOOP_DISABLED":
      return "Enable Factor Discovery flags in backend configuration.";
    case "MISSING_STATE_VERSION":
      return "Reload the page and try again.";
    case "PROVIDER_NOT_READY":
    case "LLM_CAPABILITY_FAILURE":
      return "Check Readiness for provider and LLM status.";
    default:
      return "Review the message and retry if safe.";
  }
}
