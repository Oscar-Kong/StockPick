import { describe, expect, it } from "vitest";
import {
  buildExperimentStudioHref,
  isExperimentStudioStep,
  isExperimentType,
  resolveExperimentStudioRoute,
} from "./experimentStudio";

describe("experimentStudio", () => {
  it("defaults step to choose", () => {
    const params = new URLSearchParams("section=experiments");
    expect(resolveExperimentStudioRoute(params).step).toBe("choose");
  });

  it("parses template and experiment id", () => {
    const params = new URLSearchParams("section=experiments&step=review&template=walk_forward&experiment=exp_1");
    const route = resolveExperimentStudioRoute(params);
    expect(route.step).toBe("review");
    expect(route.template).toBe("walk_forward");
    expect(route.experimentId).toBe("exp_1");
  });

  it("builds studio href", () => {
    expect(buildExperimentStudioHref({ step: "configure", template: "pairs_discovery" })).toContain(
      "template=pairs_discovery"
    );
  });

  it("validates guards", () => {
    expect(isExperimentType("factor_validation")).toBe(true);
    expect(isExperimentType("nope")).toBe(false);
    expect(isExperimentStudioStep("review")).toBe(true);
  });
});
