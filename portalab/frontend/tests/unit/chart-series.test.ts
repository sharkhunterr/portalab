import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { PALETTE_COLORS } from "../../src/design-system/themes/palettes";
import { chartSeries, colourDistance, SERIES_COUNT } from "../../src/design-system/themes/series";

// Issue 483 — whatever the palette or theme, a chart's series are told apart: films and series never the
// same colour (amber's two accents, #ffd43b and #fcc419, were one yellow). Every palette and theme Portalab
// ships, in both schemes.

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
type Pair = { name: string; scheme: "dark" | "light"; accent: string };

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? files(join(dir, entry.name))
      : entry.name.endsWith(".json")
        ? [join(dir, entry.name)]
        : [],
  );
}

function accents(): Pair[] {
  const out: Pair[] = [];
  for (const [key, schemes] of Object.entries(PALETTE_COLORS)) {
    out.push({ name: `socle:${key}`, scheme: "dark", accent: schemes.dark.accent });
    out.push({ name: `socle:${key}`, scheme: "light", accent: schemes.light.accent });
  }
  for (const file of [...files(join(ROOT, "packs")), ...files(join(ROOT, "examples/visual-packs"))]) {
    let element: Record<string, unknown>;
    try {
      element = JSON.parse(readFileSync(file, "utf8"));
    } catch {
      continue;
    }
    const palette = element.palette as Record<string, { accent?: string }> | undefined;
    for (const scheme of ["dark", "light"] as const) {
      const accent = palette?.[scheme]?.accent;
      if (accent) out.push({ name: `${file}:${scheme}`, scheme, accent });
    }
    const colors = element.colors as { accent?: string } | undefined;
    if (colors?.accent) {
      const scheme = element.colorScheme === "light" ? "light" : "dark";
      out.push({ name: file, scheme, accent: colors.accent });
    }
  }
  return out;
}

describe("chart series (issue 483)", () => {
  const all = accents();

  it("reads every palette and theme shipped", () => {
    expect(all.length).toBeGreaterThan(150);
  });

  it("keeps the accent first and tells every series apart, in every palette and theme", () => {
    const failures: string[] = [];
    for (const { name, scheme, accent } of all) {
      const series = chartSeries(accent, scheme);
      expect(series).toHaveLength(SERIES_COUNT);
      expect(series[0]).toBe(accent);
      for (let i = 0; i < series.length; i++) {
        for (let j = i + 1; j < series.length; j++) {
          const apart = colourDistance(series[i] as string, series[j] as string);
          // the first two (films and series, the most compared) far apart, the first six well apart, all ten
          // distinct (OKLab distance × 100)
          if (apart < (j === 1 ? 18 : j < 6 ? 12 : 7))
            failures.push(`${name} ${scheme}: ${series[i]} ~ ${series[j]} (${apart.toFixed(1)})`);
        }
      }
    }
    expect(failures).toEqual([]);
  });

  it("no longer uses a palette's second accent", () => {
    expect(chartSeries("#ffd43b", "dark")[1]).not.toBe("#fcc419");
    expect(colourDistance(chartSeries("#ffd43b", "dark")[1] as string, "#ffd43b")).toBeGreaterThan(18);
  });
});
