import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
// @ts-expect-error — plain ESM script without type declarations
import { offenders } from "../../scripts/check-tokens.mjs";

// 022 T006 — raw color literals in components fail the token lint; tokens and theme data may hold them.

describe("token lint", () => {
  it("flags raw colors outside the design tokens", () => {
    const root = mkdtempSync(join(tmpdir(), "tokens-"));
    mkdirSync(join(root, "features"), { recursive: true });
    mkdirSync(join(root, "design-system", "tokens"), { recursive: true });
    writeFileSync(join(root, "features", "Bad.tsx"), 'const s = { color: "#ff0000" };\n');
    writeFileSync(join(root, "features", "bad.css"), ".x { background: rgb(0, 0, 0); }\n");
    writeFileSync(join(root, "features", "Good.tsx"), 'const s = { color: "var(--color-text)" };\n');
    writeFileSync(join(root, "design-system", "tokens", "tokens.css"), ":root { --x: #ffffff; }\n");
    const found = (offenders(root) as string[]).map((line) => line.split(":")[0]);
    expect(found.sort()).toEqual([join("features", "Bad.tsx"), join("features", "bad.css")]);
  });

  it("passes on the application sources", () => {
    expect(offenders(join(process.cwd(), "src"))).toEqual([]);
  });
});
