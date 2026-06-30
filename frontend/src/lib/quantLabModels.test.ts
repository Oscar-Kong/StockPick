import { describe, expect, it } from "vitest";
import { QUANT_LAB_MODEL_CATALOG, QUANT_LAB_MODEL_IDS } from "./quantLabModels";

describe("quantLabModels", () => {
  it("defines five canonical models with equations", () => {
    expect(QUANT_LAB_MODEL_IDS).toEqual(["gbm", "hmm", "markowitz", "cointegration", "garch"]);
    expect(QUANT_LAB_MODEL_CATALOG).toHaveLength(5);
    for (const model of QUANT_LAB_MODEL_CATALOG) {
      expect(model.equations.length).toBeGreaterThanOrEqual(3);
      for (const eq of model.equations) {
        expect(eq.tex.length).toBeGreaterThan(0);
      }
    }
  });
});
