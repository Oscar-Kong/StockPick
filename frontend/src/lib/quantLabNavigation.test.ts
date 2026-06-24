import { describe, expect, it } from "vitest";
import {
  buildQuantLabHref,
  isQuantLabLegacyTab,
  isQuantLabSection,
  resolveQuantLabRoute,
} from "./quantLabNavigation";

describe("quantLabNavigation", () => {
  it("defaults to overview", () => {
    const params = new URLSearchParams("");
    expect(resolveQuantLabRoute(params).section).toBe("overview");
  });

  it("maps legacy tab-only URLs", () => {
    const params = new URLSearchParams("tab=walk-forward");
    const route = resolveQuantLabRoute(params);
    expect(route.section).toBe("legacy");
    expect(route.legacyTab).toBe("walk-forward");
  });

  it("falls back unknown section to overview", () => {
    const params = new URLSearchParams("section=unknown");
    expect(resolveQuantLabRoute(params).section).toBe("overview");
  });

  it("builds href with section and legacy tab", () => {
    expect(buildQuantLabHref("legacy", { legacyTab: "pairs" })).toContain("section=legacy");
    expect(buildQuantLabHref("legacy", { legacyTab: "pairs" })).toContain("tab=pairs");
  });

  it("validates section and tab guards", () => {
    expect(isQuantLabSection("ideas")).toBe(true);
    expect(isQuantLabSection("nope")).toBe(false);
    expect(isQuantLabLegacyTab("factor-performance")).toBe(true);
    expect(isQuantLabLegacyTab("nope")).toBe(false);
  });
});
