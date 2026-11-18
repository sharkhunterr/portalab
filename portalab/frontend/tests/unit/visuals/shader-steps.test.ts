import { describe, expect, it } from "vitest";
import { STEPS } from "../../../src/design-system/themes/premium/shaderRunner";

// Issue 506 — an ambience on a struggling device gives up frames before sharpness, and never draws below
// 62 % of the device pixels (it fell to 36 %: a blurred background on older phones).

describe("an ambience's steps when frames come late", () => {
  it("starts sharp at 30 frames a second", () => {
    expect(STEPS[0]).toEqual({ scale: 1, fps: 30 });
  });

  it("lowers the frames before the resolution", () => {
    const firstBlur = STEPS.findIndex((step) => step.scale < 1);
    expect(firstBlur).toBeGreaterThan(0);
    expect(STEPS.slice(0, firstBlur).every((step) => step.scale === 1)).toBe(true);
    expect(STEPS[firstBlur - 1]?.fps).toBeLessThanOrEqual(15);
  });

  it("never draws below 62 % of the device pixels, each step lighter than the last", () => {
    expect(Math.min(...STEPS.map((step) => step.scale))).toBeGreaterThanOrEqual(0.62);
    for (let i = 1; i < STEPS.length; i++) {
      const [before, after] = [STEPS[i - 1], STEPS[i]] as [(typeof STEPS)[number], (typeof STEPS)[number]];
      expect(after.scale * after.fps).toBeLessThan(before.scale * before.fps);
    }
  });
});
