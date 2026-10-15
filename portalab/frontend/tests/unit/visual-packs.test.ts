import { describe, expect, it } from "vitest";
import {
  interfaceSelectorOk,
  lookSelectorOk,
  shieldSelector,
  splitSelectors,
} from "../../src/design-system/themes/external/cssGuard";
import { safeAssetPath } from "../../src/design-system/themes/external/sandbox";

/** issue 1: what an imported pack may style, and which of its files its sandbox may ask for. */
describe("visual packs — CSS guard", () => {
  it("splits selector lists without breaking :is() or attribute values", () => {
    expect(splitSelectors('a, b:is(c, d), [data-x="1,2"]')).toEqual(["a", "b:is(c, d)", '[data-x="1,2"]']);
  });

  it("keeps a look on its own element", () => {
    expect(lookSelectorOk('.avatar-frame[data-frame="x"]', "x")).toBe(true);
    expect(lookSelectorOk('.avatar-frame[data-frame="x"]::before', "x")).toBe(true);
    expect(lookSelectorOk('.avatar-frame[data-frame="x"] .inner', "x")).toBe(true);
    expect(lookSelectorOk('.avatar-frame[data-frame="x"] ~ .price', "x")).toBe(false);
    expect(lookSelectorOk('.avatar-frame[data-frame="x"] + *', "x")).toBe(false);
    expect(lookSelectorOk('body [data-frame="x"]', "x")).toBe(false);
    expect(lookSelectorOk('.dialog:has([data-frame="x"])', "x")).toBe(false);
    expect(lookSelectorOk(".purchase-bar", "x")).toBe(false);
  });

  it("keeps an interface under its key and away from protected surfaces", () => {
    expect(interfaceSelectorOk('[data-theme="n"] .shell-header', "n")).toBe(true);
    expect(interfaceSelectorOk(".shell-header", "n")).toBe(false);
    expect(interfaceSelectorOk('[data-theme="other"] .x', "n")).toBe(false);
    expect(shieldSelector('[data-theme="n"] .card')).toBe(
      '[data-theme="n"] .card:not([data-protected]):not([data-protected] *)',
    );
    expect(shieldSelector('[data-theme="n"] .card::before')).toBe(
      '[data-theme="n"] .card:not([data-protected]):not([data-protected] *)::before',
    );
  });
});

describe("visual packs — sandbox files", () => {
  it("serves the sandbox only files inside its own element", () => {
    expect(safeAssetPath("font.woff2")).toBe("font.woff2");
    expect(safeAssetPath("./img/a.png")).toBe("img/a.png");
    for (const path of ["../pack.json", "/etc/passwd", "a/../../b", "https://example.org/x", "a\\b", "", 3]) {
      expect(safeAssetPath(path)).toBeNull();
    }
  });
});
