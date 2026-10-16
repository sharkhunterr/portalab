import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseTheme, themeJsonSchema } from "../../src/design-system/themes/schema";
import { BUILTIN_THEMES } from "../support/themes";

// 022 T005 — closed theme schema: valid passes; unknown keys, script/URL values, missing state rejected.
// The JSON Schema shared with the backend must match (regenerate with UPDATE_THEME_SCHEMA=1).

const SHARED = join(
  process.cwd(),
  "..",
  "backend",
  "src",
  "portalab",
  "modules",
  "ui",
  "themes",
  "theme.schema.json",
);
const base = () => structuredClone(BUILTIN_THEMES[0]) as Record<string, unknown>;

describe("theme schema", () => {
  it("accepts the built-in themes", () => {
    for (const theme of BUILTIN_THEMES) {
      expect(parseTheme(theme).errors).toEqual([]);
    }
  });

  it("rejects unknown keys", () => {
    expect(parseTheme({ ...base(), css: "body{}" }).errors.join()).toMatch(/css|Unrecognized/i);
    const colors = { ...(base().colors as object), glow: "#fff" };
    expect(parseTheme({ ...base(), colors }).errors.length).toBeGreaterThan(0);
  });

  it("rejects scripts and external URLs", () => {
    const colors = { ...(base().colors as object), surface: "url(javascript:alert(1))" };
    expect(parseTheme({ ...base(), colors }).errors.length).toBeGreaterThan(0);
    for (const image of [
      "https://evil.example/x.png",
      "data:image/svg+xml;base64,PHN2Zz4=",
      "javascript:alert(1)",
    ]) {
      expect(
        parseTheme({ ...base(), background: { image, fallback: "#ffffff" } }).errors.length,
        image,
      ).toBeGreaterThan(0);
    }
    expect(parseTheme({ ...base(), sounds: { alert: "https://x/beep.mp3" } }).errors.length).toBeGreaterThan(
      0,
    );
    expect(
      parseTheme({ ...base(), typography: { fontFamily: "x; } body { display:none" } }).errors.length,
    ).toBeGreaterThan(0);
  });

  it("requires every functional state and no extra state", () => {
    const states = { ...(base().states as Record<string, unknown>) };
    delete states.maintenance;
    expect(parseTheme({ ...base(), states }).errors.join()).toMatch(/maintenance/);
    const extra = { ...(base().states as Record<string, unknown>), celebrating: { fg: "#000", bg: "#fff" } };
    expect(parseTheme({ ...base(), states: extra }).errors.length).toBeGreaterThan(0);
  });

  it("matches the JSON Schema shared with the backend", () => {
    const current = `${JSON.stringify(themeJsonSchema(), null, 2)}\n`;
    if (process.env.UPDATE_THEME_SCHEMA) {
      writeFileSync(SHARED, current);
    }
    expect(readFileSync(SHARED, "utf8")).toBe(current);
  });
});
