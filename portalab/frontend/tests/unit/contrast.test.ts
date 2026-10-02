import { describe, expect, it } from "vitest";
import {
  contrast,
  isColor,
  LARGE_OR_UI_MIN,
  parseColor,
  TEXT_MIN,
} from "../../src/design-system/themes/contrast";

// 022 T004 — WCAG ratios against reference values; thresholds; alpha compositing over the background.

describe("contrast", () => {
  it("matches reference ratios", () => {
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 1);
    expect(contrast("#ffffff", "#ffffff")).toBeCloseTo(1, 5);
    expect(contrast("#767676", "#ffffff")).toBeCloseTo(4.54, 2);
    expect(contrast("#777777", "#ffffff")).toBeLessThan(TEXT_MIN);
    expect(contrast("#949494", "#ffffff")).toBeGreaterThanOrEqual(LARGE_OR_UI_MIN);
    expect(contrast("#ffffff", "#000")).toBeCloseTo(21, 1);
  });

  it("is symmetric and composites alpha over the background", () => {
    expect(contrast("#1f4fd1", "#ffffff")).toBeCloseTo(contrast("#ffffff", "#1f4fd1"), 5);
    expect(contrast("rgba(0, 0, 0, 0.5)", "#ffffff")).toBeCloseTo(contrast("#808080", "#ffffff"), 1);
    expect(contrast("#000000", "#00000000", "#ffffff")).toBeCloseTo(21, 1); // transparent bg shows the base
  });

  it("parses supported color syntaxes only", () => {
    expect(parseColor("#abc")).toEqual({ r: 170, g: 187, b: 204, a: 1 });
    expect(parseColor("#11223380").a).toBeCloseTo(0.5, 1);
    expect(isColor("rgb(1, 2, 3)")).toBe(true);
    expect(isColor("url(javascript:alert(1))")).toBe(false);
    expect(isColor("red")).toBe(false);
  });
});
