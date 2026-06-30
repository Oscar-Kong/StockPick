import { describe, expect, it } from "vitest";
import {
  correlationStrength,
  correlationStrengthLabel,
  formatCorrelationCellAria,
} from "./correlationLabels";

const messages = {
  perfect: "Same symbol",
  strongPositive: "Strong positive correlation",
  moderatePositive: "Moderate positive correlation",
  weakPositive: "Weak positive correlation",
  negligible: "Low correlation",
  weakNegative: "Weak negative correlation",
  moderateNegative: "Moderate negative correlation",
  strongNegative: "Strong negative correlation",
  cellAria: "{a} and {b}. Correlation: {value}. {strength}",
};

describe("correlationLabels", () => {
  it("classifies strength by magnitude and sign", () => {
    expect(correlationStrength(0.9, false)).toBe("strong_positive");
    expect(correlationStrength(-0.72, false)).toBe("moderate_negative");
    expect(correlationStrength(1, true)).toBe("perfect");
  });

  it("formats accessible cell label", () => {
    const label = formatCorrelationCellAria("AAPL", "MSFT", 0.74, false, messages);
    expect(label).toContain("AAPL");
    expect(label).toContain("MSFT");
    expect(label).toContain("0.74");
    expect(label).toContain("Moderate positive correlation");
  });

  it("returns strength label text", () => {
    expect(correlationStrengthLabel("strong_positive", messages)).toBe("Strong positive correlation");
  });
});
