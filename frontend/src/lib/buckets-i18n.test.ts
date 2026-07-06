import { describe, expect, it } from "vitest";
import { normalizeBucket, parseBucket } from "./buckets-i18n";

describe("normalizeBucket", () => {
  it("maps legacy medium to penny", () => {
    expect(normalizeBucket("medium")).toBe("penny");
    expect(parseBucket("medium")).toBe("penny");
  });

  it("preserves active buckets", () => {
    expect(normalizeBucket("compounder")).toBe("compounder");
    expect(normalizeBucket("penny")).toBe("penny");
  });
});
