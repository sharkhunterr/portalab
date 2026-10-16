#!/usr/bin/env node
/**
 * 028 B2 (T036, R8): moves Portalab's palettes' colours into their built-in pack elements (``render: data``,
 * ``palette: {dark: {accent, accentAlt, contrast}, light: {…}}``) — the socle's stay in the code too, drawn
 * before any pack is read (first paint).
 *
 *   node scripts/extract-builtin-palettes.mjs [--dry-run]
 *
 * Run once (2026-10-16): what it moved is no longer in the code — the packs are now the looks' source, and
 * this script stays as the record of how they were moved.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONT = resolve(HERE, "..");
const PACKS = resolve(FRONT, "..", "packs", "builtin");
const dry = process.argv.includes("--dry-run");

const scratch = mkdtempSync(join(tmpdir(), "portalab-palettes-"));
const entry = join(scratch, "entry.ts");
writeFileSync(
  entry,
  `export { PALETTE_COLORS } from ${JSON.stringify(join(FRONT, "src", "design-system", "themes", "palettes"))};\n`,
);
execFileSync(join(FRONT, "node_modules", ".bin", "esbuild"), [
  entry,
  "--bundle",
  "--format=esm",
  "--platform=node",
  "--log-level=error",
  `--outfile=${join(scratch, "palettes.mjs")}`,
]);
const { PALETTE_COLORS } = await import(pathToFileURL(join(scratch, "palettes.mjs")).href);
rmSync(scratch, { recursive: true, force: true });

const found = new Set();
for (const pack of readdirSync(PACKS)) {
  const elements = join(PACKS, pack, "elements");
  if (!existsSync(elements)) continue;
  for (const folder of readdirSync(elements)) {
    const file = join(elements, folder, "element.json");
    const element = JSON.parse(readFileSync(file, "utf8"));
    const colours = element.type === "palette" ? PALETTE_COLORS[element.look] : undefined;
    if (!colours) continue;
    found.add(element.look);
    element.render = { kind: "data" };
    element.palette = colours;
    if (!dry) writeFileSync(file, `${JSON.stringify(element, null, 2)}\n`);
  }
}
const missing = Object.keys(PALETTE_COLORS).filter((look) => !found.has(look));
console.log(JSON.stringify({ written: found.size, missing }, null, 1));
