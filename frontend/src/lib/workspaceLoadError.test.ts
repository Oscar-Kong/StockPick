import { describe, expect, it } from "vitest";
import { en } from "@/lib/i18n/messages/en";
import { explainAnalysisLoadError, explainWorkspaceLoadError } from "./workspaceLoadError";

describe("explainWorkspaceLoadError", () => {
  it("explains unreachable backend", () => {
    const msg = explainWorkspaceLoadError(new Error("Failed to fetch"), en);
    expect(msg).toContain("Browser could not complete");
    expect(msg).toContain("127.0.0.1:18731");
  });

  it("explains timeout", () => {
    const msg = explainWorkspaceLoadError(new Error("Request timed out after 30s"), en);
    expect(msg).toContain("timed out");
  });

  it("passes through API detail", () => {
    const msg = explainWorkspaceLoadError(new Error('{"detail":"watchlist table missing"}'), en);
    expect(msg).toContain("watchlist table missing");
  });

  it("explains analysis load for symbol", () => {
    const msg = explainAnalysisLoadError(new Error("Failed to fetch"), en, "CLOV");
    expect(msg).toContain("CLOV");
    expect(msg).toContain("Could not load");
    expect(msg).toContain("127.0.0.1:18731");
  });
});
