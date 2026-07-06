import { getApiBaseUrl } from "../apiConfig";
import { parseApiError } from "../apiError";

const DEFAULT_REQUEST_TIMEOUT_MS = 45_000;

/** Resolve API base per request (supports relative URLs + Next rewrites when unset). */
export function resolveApiBaseUrl(): string {
  return getApiBaseUrl();
}

export async function request<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const { timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, signal: callerSignal, ...rest } = init ?? {};
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  if (callerSignal) {
    if (callerSignal.aborted) {
      controller.abort();
    } else {
      callerSignal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }

  try {
    const res = await fetch(`${resolveApiBaseUrl()}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...rest.headers,
      },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(parseApiError(new Error(text || `Request failed: ${res.status}`)));
    }
    return res.json() as Promise<T>;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/** @deprecated Use resolveApiBaseUrl() — module-load URL breaks production when env is set at runtime. */
export const API_URL = resolveApiBaseUrl();

export { DEFAULT_REQUEST_TIMEOUT_MS };
