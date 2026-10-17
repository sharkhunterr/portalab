#!/usr/bin/env node
/**
 * 028 B2 (T036, R8): moves Portalab's own GPU looks into their built-in pack elements, as their CSS looks
 * went (``extract-builtin-packs.mjs``).
 *
 * Each look the interface drew with one of its effects (``premium/fxLooks.ts``: level badges, notification,
 * title and badge styles, name auras, notification bursts, celebrations, level-ups, avatar frames) gets the
 * effect's fragment (``premium/badgeFx.ts``, the same contract as an imported pack's) in its element's folder,
 * and is drawn by it: ``render: {kind: "glsl", file, shape, radius, stage, start, cycle}`` — its stylesheet,
 * if it has one, kept beside it. The interface then finds every GPU look through its packs, Portalab's own
 * included. The packs are their source since (``backend/scripts/stamp_builtin_packs.py`` stamps their
 * versions).
 *
 *   node scripts/extract-builtin-gpu.mjs [--dry-run]
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
const PREMIUM = join(FRONT, "src", "design-system", "themes", "premium");
const dry = process.argv.includes("--dry-run");

// the tables and the effects' fragments, as the interface has them
const scratch = mkdtempSync(join(tmpdir(), "portalab-gpu-"));
const entry = join(scratch, "entry.ts");
writeFileSync(
  entry,
  `export * from ${JSON.stringify(join(PREMIUM, "fxLooks"))};\nexport { EFFECTS } from ${JSON.stringify(join(PREMIUM, "badgeFx"))};\n`,
);
execFileSync(join(FRONT, "node_modules", ".bin", "esbuild"), [
  entry,
  "--bundle",
  "--format=esm",
  "--platform=node",
  "--log-level=error",
  `--outfile=${join(scratch, "fx.mjs")}`,
]);
const fx = await import(pathToFileURL(join(scratch, "fx.mjs")).href);
rmSync(scratch, { recursive: true, force: true });

/** per type: look → how it is drawn */
const plans = {
  level_badge: Object.fromEntries(
    Object.entries(fx.FX_LEVEL_BADGES).map(([look, effect]) => [look, { effect }]),
  ),
  notification_style: Object.fromEntries(
    Object.entries(fx.FX_STYLES).map(([look, effect]) => [
      look,
      { effect, shape: fx.FX_NOTIFICATION_SHAPES[look] ?? 0 },
    ]),
  ),
  title: Object.fromEntries(Object.entries(fx.FX_STYLES).map(([look, effect]) => [look, { effect }])),
  badge: Object.fromEntries(Object.entries(fx.FX_STYLES).map(([look, effect]) => [look, { effect }])),
  name_style: Object.fromEntries(Object.entries(fx.FX_NAMES).map(([look, effect]) => [look, { effect }])),
  notification_animation: Object.fromEntries(
    Object.entries(fx.FX_NOTIFICATION_ANIMATIONS).map(([look, effect]) => [look, { effect }]),
  ),
  effect: Object.fromEntries(
    Object.entries(fx.FX_CELEBRATIONS).map(([look, { effect, from }]) => [
      look,
      { effect, stage: true, start: from },
    ]),
  ),
  level_up: Object.fromEntries([...fx.FX_LEVEL_UPS].map((look) => [look, { effect: look, stage: true }])),
  avatar_frame: Object.fromEntries(
    Object.entries(fx.FX_FRAMES).map(([look, spec]) => [
      look,
      { effect: spec.effect, shape: spec.shape ?? 0, ...(spec.radius ? { radius: spec.radius } : {}) },
    ]),
  ),
};

const found = new Set();
let written = 0;
for (const pack of readdirSync(PACKS)) {
  const elements = join(PACKS, pack, "elements");
  if (!existsSync(elements)) continue;
  for (const folder of readdirSync(elements)) {
    const file = join(elements, folder, "element.json");
    const element = JSON.parse(readFileSync(file, "utf8"));
    const plan = element.look ? plans[element.type]?.[element.look] : undefined;
    if (!plan) continue;
    const body = fx.EFFECTS[plan.effect];
    if (!body) throw new Error(`${element.type}/${element.look}: no effect « ${plan.effect} »`);
    found.add(`${element.type}/${element.look}`);
    const css = element.render?.kind === "css" ? (element.render.css ?? []) : [];
    element.render = {
      kind: "glsl",
      file: `${plan.effect}.glsl`,
      ...(css.length ? { css } : {}),
      ...(plan.stage ? { stage: true } : {}),
      ...(plan.shape ? { shape: plan.shape } : {}),
      ...(plan.radius ? { radius: plan.radius } : {}),
      ...(plan.start ? { start: plan.start } : {}),
      ...(plan.effect === "chrono" ? { cycle: true } : {}),
    };
    written += 1;
    if (dry) continue;
    writeFileSync(
      join(elements, folder, `${plan.effect}.glsl`),
      `// Portalab — ${element.type}/${element.look}: the « ${plan.effect} » effect (spec 028, B2)\n${body.replace(/^\n/, "")}`,
    );
    writeFileSync(file, `${JSON.stringify(element, null, 2)}\n`);
  }
}
const missing = Object.entries(plans).flatMap(([type, looks]) =>
  Object.keys(looks)
    .filter((look) => !found.has(`${type}/${look}`) && type !== "title" && type !== "badge")
    .map((look) => `${type}/${look}`),
);
console.log(JSON.stringify({ written, missing }, null, 1));
