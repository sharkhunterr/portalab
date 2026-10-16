import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { contrast, LARGE_OR_UI_MIN, TEXT_MIN } from "../../src/design-system/themes/contrast";
import { PALETTE_COLORS } from "../../src/design-system/themes/palettes";

// 027 — every palette offered has accent colours in both schemes, no two palettes share an accent, and
// each stays readable: the accent on a plain light or dark page, its contrast colour on the accent.

// 028: the palettes offered are those Portalab's own packs hold (none is listed in the interface's code)
const PACKS = resolve(dirname(fileURLToPath(import.meta.url)), "../../../packs/builtin");
const PALETTE_KEYS = readdirSync(PACKS).flatMap((pack) =>
  readdirSync(join(PACKS, pack, "elements")).flatMap((folder) => {
    const element = JSON.parse(readFileSync(join(PACKS, pack, "elements", folder, "element.json"), "utf8"));
    return element.type === "palette" && element.look ? [element.look as string] : [];
  }),
);

describe("palettes", () => {
  it("covers every palette key, without duplicates", () => {
    expect(PALETTE_KEYS.length).toBeGreaterThan(40);
    const seen = new Set<string>();
    for (const key of PALETTE_KEYS.filter((k) => k !== "theme")) {
      const palette = PALETTE_COLORS[key];
      expect(palette, key).toBeDefined();
      const pair = `${palette?.dark.accent}/${palette?.dark.accentAlt}`;
      expect(seen.has(pair), `${key} repeats ${pair}`).toBe(false);
      seen.add(pair);
    }
  });

  it("keeps accents readable", () => {
    for (const [key, schemes] of Object.entries(PALETTE_COLORS)) {
      const page = { dark: "#0f1117", light: "#ffffff" } as const;
      for (const scheme of ["dark", "light"] as const) {
        const palette = schemes[scheme];
        expect(contrast(palette.accent, page[scheme]), `${key}/${scheme}`).toBeGreaterThanOrEqual(
          LARGE_OR_UI_MIN,
        );
        expect(
          contrast(palette.contrast, palette.accent),
          `${key}/${scheme} on accent`,
        ).toBeGreaterThanOrEqual(TEXT_MIN);
      }
    }
  });
});
