import { describe, expect, it } from "vitest";
import {
  frameInterval,
  liveAmbiences,
  liveLooks,
  motionBudget,
  setMotionChoice,
} from "../../src/design-system/motion/budget";

/** #29: the member's choice and reduced motion set how much decorative motion the portal spends. */
describe("motion budget", () => {
  it("follows the member's choice, reduced motion first", () => {
    setMotionChoice("all", false);
    expect(motionBudget()).toBe("full");
    expect(document.documentElement.dataset.motionBudget).toBe("full");
    expect(frameInterval()).toBeCloseTo(1000 / 30);
    const full = liveLooks();

    setMotionChoice("discreet", false);
    expect(motionBudget()).toBe("eco");
    expect(liveLooks()).toBeLessThan(full);
    expect(liveAmbiences()).toBeGreaterThanOrEqual(2); // the page's ambience and a banner in view
    expect(frameInterval()).toBeCloseTo(1000 / 15);

    setMotionChoice("none", false);
    expect(motionBudget()).toBe("still");
    expect(liveLooks()).toBe(0);
    expect(liveAmbiences()).toBe(0);

    setMotionChoice("all", true); // reduced motion wins over « all »
    expect(motionBudget()).toBe("still");
    setMotionChoice("all", false);
  });
});
