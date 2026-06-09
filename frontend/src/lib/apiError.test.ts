import { describe, expect, it } from "vitest";
import { isFeatureDisabledError, parseApiError } from "./apiError";

describe("parseApiError", () => {
  it("extracts FastAPI detail string", () => {
    expect(parseApiError(new Error('{"detail":"SCORE_ENGINE_V2_ENABLED is false"}'))).toBe(
      "SCORE_ENGINE_V2_ENABLED is false"
    );
  });

  it("falls back to message text", () => {
    expect(parseApiError(new Error("network failure"))).toBe("network failure");
  });

  it("uses fallback for non-Error", () => {
    expect(parseApiError(null, "oops")).toBe("oops");
  });
});

describe("isFeatureDisabledError", () => {
  it("detects 503 and feature flag messages", () => {
    expect(isFeatureDisabledError('{"detail":"503 Service Unavailable"}')).toBe(true);
    expect(isFeatureDisabledError("SCORE_ENGINE_V2_ENABLED is false")).toBe(true);
    expect(isFeatureDisabledError("network timeout")).toBe(false);
  });
});
