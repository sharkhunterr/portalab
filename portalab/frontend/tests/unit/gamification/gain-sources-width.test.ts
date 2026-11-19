import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Issue 507 — on a phone, « where my XP comes from » stays its card's width: its grids keep one column the
// card's width (an implicit auto column grew to the level-ups row, and the chart with it) and its tabs scroll.
// jsdom lays nothing out, so the rules themselves are checked; the LAN was measured at 355 px.

const css = readFileSync(join(process.cwd(), "src/features/gamification/gamification.css"), "utf8");

function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const found = css.match(new RegExp(`(^|\\n)${escaped} \\{([^}]*)\\}`));
  return found?.[2] ?? "";
}

describe("the gains card on a phone", () => {
  it("keeps the chart and the level-ups within one column the card's width", () => {
    expect(rule(".gain-sources")).toContain("grid-template-columns: minmax(0, 1fr)");
    expect(rule(".gain-timeline")).toContain("grid-template-columns: minmax(0, 1fr)");
    expect(rule(".gain-levelups")).toContain("min-inline-size: 0");
    expect(rule(".gain-levelups ol")).toContain("overflow-x: auto");
  });

  it("lets its tabs scroll rather than widen the card", () => {
    expect(rule(".gain-sources__filters")).toContain("min-inline-size: 0");
  });
});
