import { readFileSync } from "node:fs";
import { render } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { FUNCTIONAL_STATES, FunctionalState, STATE_LABELS } from "../../src/design-system/FunctionalState";

// T053 — every functional state renders with a non-color cue (icon + text) and passes axe under two token
// sets; color contrast of every token pair is checked against WCAG 2.2 AA; reduced motion is honored.

const read = (relative: string) => readFileSync(new URL(relative, import.meta.url), "utf8");
const THEMES = {
  light: read("../../src/design-system/themes/light.css"),
  dark: read("../../src/design-system/themes/dark.css"),
};
const TOKENS = read("../../src/design-system/tokens.css");

function colorTokens(css: string): Map<string, string> {
  const tokens = new Map<string, string>();
  for (const match of css.matchAll(/(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    tokens.set(match[1] as string, (match[2] as string).toLowerCase());
  }
  return tokens;
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [
    number,
    number,
    number,
  ];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const AA_TEXT = 4.5;

describe.each(Object.entries(THEMES))("%s theme", (theme, css) => {
  const tokens = colorTokens(css);

  it("redefines exactly the same color tokens as the base set (appearance only)", () => {
    expect([...tokens.keys()].sort()).toEqual([...colorTokens(TOKENS).keys()].sort());
  });

  it.each(FUNCTIONAL_STATES)("state %s meets WCAG AA contrast", (state) => {
    const fg = tokens.get(`--state-${state}-fg`) as string;
    const bg = tokens.get(`--state-${state}-bg`) as string;
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(AA_TEXT);
  });

  it("text and accent pairs meet WCAG AA contrast", () => {
    const pairs: [string, string][] = [
      ["--color-text", "--color-surface"],
      ["--color-text", "--color-surface-raised"],
      ["--color-text-muted", "--color-surface"],
      ["--color-accent-contrast", "--color-accent"],
    ];
    for (const [fg, bg] of pairs) {
      expect(
        contrast(tokens.get(fg) as string, tokens.get(bg) as string),
        `${fg} on ${bg}`,
      ).toBeGreaterThanOrEqual(AA_TEXT);
    }
  });

  it.each(FUNCTIONAL_STATES)("state %s has icon + text and no axe violation", async (state) => {
    const { container } = render(
      <div data-theme={theme} lang="en">
        <main>
          <FunctionalState state={state} detail="Services" onRetry={() => undefined} />
        </main>
      </div>,
    );
    const element = container.querySelector(`[data-state="${state}"]`) as HTMLElement;
    expect(element).not.toBeNull();
    expect(element.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(element).toHaveTextContent(STATE_LABELS[state]);
    expect(element.getAttribute("role")).toMatch(/^(status|alert)$/);
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});

describe("motion", () => {
  it("prefers-reduced-motion disables animations and transitions globally", () => {
    const block = TOKENS.slice(TOKENS.indexOf("@media (prefers-reduced-motion: reduce)"));
    expect(block).toContain("animation-duration: 0.01ms !important");
    expect(block).toContain("transition-duration: 0.01ms !important");
    expect(block).toContain("--motion-duration-normal: 0ms");
  });
});
