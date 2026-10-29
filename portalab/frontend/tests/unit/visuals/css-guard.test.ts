import { describe, expect, it } from "vitest";
import {
  animationSuffix,
  interfaceSelectorOk,
  lookSelectorOk,
  namespaceAnimations,
  shieldSelector,
  splitSelectors,
} from "../../../src/design-system/visuals/cssGuard";
import { safeAssetPath } from "../../../src/design-system/visuals/sandbox";

/** 028: what a pack may style, and which of its files its sandbox may ask for. */
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

describe("visual packs — names of their own", () => {
  it("gives a pack's keyframes a suffix and rewrites the animations naming them", () => {
    const suffix = animationSuffix({ pack: "abysses", type: "avatar_frame", look: "corail" });
    expect(suffix).toBe("--abysses-avatar_frame-corail".replace(/_/g, "-"));
    const css = namespaceAnimations(
      "@keyframes glow { to { opacity: 1 } } .a { animation: glow 2s infinite, spin 1s; animation-name: glow }",
      "--x",
    );
    expect(css).toContain("@keyframes glow--x");
    expect(css).toContain("animation: glow--x 2s infinite, spin 1s");
    expect(css).toContain("animation-name: glow--x");
  });

  it("leaves a sheet without keyframes as it is", () => {
    const css = ".a { animation: spin 1s }";
    expect(namespaceAnimations(css, "--x")).toBe(css);
  });
});

describe("visual packs — sandbox files", () => {
  it("serves the sandbox only files inside its own element", () => {
    expect(safeAssetPath("font.woff2")).toBe("font.woff2");
    expect(safeAssetPath("./img/a.png")).toBe("img/a.png");
    // issue 279: escapes too — « %2e%2e » is « .. » once the browser reads the address
    for (const path of [
      "../pack.json",
      "/etc/passwd",
      "a/../../b",
      "https://example.org/x",
      "a\\b",
      "",
      3,
      "%2e%2e/%2e%2e/me",
      "nav/%2E%2e/x",
      "a%2fb",
      "%5c",
    ]) {
      expect(safeAssetPath(path)).toBeNull();
    }
  });

  it("028: accepts the hook of an element wearing several looks (~=), never a sibling", () => {
    expect(lookSelectorOk('.widget-frame[data-widget-option~="houle"]::after', "houle")).toBe(true);
    expect(lookSelectorOk('[data-widget-option~="houle"] .widget-rows', "houle")).toBe(true);
    expect(lookSelectorOk('[data-widget-option~="houle"] ~ .widget-frame', "houle")).toBe(false);
    expect(lookSelectorOk('[data-widget-option~="other"]', "houle")).toBe(false);
  });

  it("028: an nth formula is no combinator, a sibling in its « of S » part still is", () => {
    expect(lookSelectorOk('[data-ambient="x"] > span:nth-child(3n + 1)', "x")).toBe(true);
    expect(lookSelectorOk('[data-ambient="x"] > span:nth-child(-n + 2)::after', "x")).toBe(true);
    expect(lookSelectorOk('[data-ambient="x"] > span:nth-child(2n of .a + .b)', "x")).toBe(false);
  });
});
