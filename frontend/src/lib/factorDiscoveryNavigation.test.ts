import { describe, expect, it } from "vitest";
import {
  buildFactorDiscoveryHref,
  buildQuantLabHref,
  isFactorDiscoveryView,
  resolveFactorDiscoveryView,
} from "./quantLabNavigation";
import { formatMiningStatus, readinessEntryState } from "./api/factorDiscovery/formatters";

describe("factor discovery navigation", () => {
  it("includes factor-discovery section in href", () => {
    expect(buildQuantLabHref("factor-discovery")).toContain("section=factor-discovery");
  });

  it("builds factor discovery sub-view href", () => {
    expect(buildFactorDiscoveryHref("new-research")).toContain("fdView=new-research");
  });

  it("validates fd views", () => {
    expect(isFactorDiscoveryView("sessions")).toBe(true);
    expect(isFactorDiscoveryView("nope")).toBe(false);
  });

  it("defaults fd view to sessions", () => {
    expect(resolveFactorDiscoveryView(new URLSearchParams(""))).toBe("sessions");
  });
});

describe("factor discovery formatters", () => {
  it("formats status labels for humans", () => {
    expect(formatMiningStatus("AWAITING_HYPOTHESIS_REVIEW")).toBe("Awaiting hypothesis review");
  });

  it("detects disabled readiness", () => {
    expect(
      readinessEntryState({
        mining_loop_enabled: false,
        factor_discovery_enabled: false,
        supervised_ready: false,
        blocking_reasons: [],
      })
    ).toBe("disabled");
  });

  it("detects supervised readiness", () => {
    expect(
      readinessEntryState({
        mining_loop_enabled: true,
        factor_discovery_enabled: true,
        supervised_ready: true,
        blocking_reasons: [],
      })
    ).toBe("supervised");
  });
});
