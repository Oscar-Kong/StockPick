import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getApiBaseUrl,
  isBackendWakingError,
  isDemoDisabledError,
  requireApiBaseUrl,
} from "./apiConfig";

describe("apiConfig", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("normalizes trailing slash", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com/");
    expect(getApiBaseUrl()).toBe("https://api.example.com");
  });

  it("falls back locally when unset in development", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "development");
    expect(getApiBaseUrl()).toContain("127.0.0.1");
  });

  it("uses relative URLs in production when unset (Next rewrites proxy)", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    expect(getApiBaseUrl()).toBe("");
  });

  it("requires URL in production", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    expect(() => requireApiBaseUrl()).toThrow(/NEXT_PUBLIC_API_URL/);
  });

  it("detects waking and demo-disabled errors", () => {
    expect(isBackendWakingError("Failed to fetch")).toBe(true);
    expect(isDemoDisabledError("This action is disabled in the public demo.")).toBe(true);
  });
});
