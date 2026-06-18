/** Central API base URL for browser and server code. */
const LOCAL_FALLBACK = "http://127.0.0.1:18731";

export function getApiBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
    "";
  if (raw) {
    return raw.replace(/\/$/, "");
  }
  if (process.env.NODE_ENV === "production") {
    return "";
  }
  return LOCAL_FALLBACK;
}

export function requireApiBaseUrl(): string {
  const url = getApiBaseUrl();
  if (!url) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not configured. Set it to your Render backend URL in Vercel.",
    );
  }
  return url;
}

export const HEALTH_CHECK_TIMEOUT_MS = 12_000;
export const HEALTH_RETRY_ATTEMPTS = 4;
export const HEALTH_RETRY_DELAY_MS = 2_500;

/** Scan job kickoff — may wait for demo guards / DB before returning job id. */
export const SCAN_REQUEST_TIMEOUT_MS = 120_000;
/** Each poll is a lightweight in-memory status read. */
export const SCAN_STATUS_REQUEST_TIMEOUT_MS = 60_000;

export function isBackendWakingError(message: string): boolean {
  const m = message.toLowerCase();
  return (
    m.includes("failed to fetch") ||
    m.includes("network") ||
    m.includes("load failed") ||
    m.includes("timed out") ||
    m.includes("502") ||
    m.includes("503") ||
    m.includes("504")
  );
}

export function isDemoDisabledError(message: string): boolean {
  const m = message.toLowerCase();
  return m.includes("demo_action_disabled") || m.includes("disabled in the public demo");
}
