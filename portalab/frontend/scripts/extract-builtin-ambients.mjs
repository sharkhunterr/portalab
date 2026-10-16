#!/usr/bin/env node
/**
 * 028 B2 (T036, T038, R8, R9): moves Portalab's premium ambiences into their built-in pack elements, as its CSS
 * and GPU looks went (``extract-builtin-packs.mjs``, ``extract-builtin-gpu.mjs``).
 *
 * Each premium ambience (``premium/PremiumAmbient.tsx``) is layers: a shader (a whole program after
 * ``COMMON``: ``premium/{shaders,cozyShaders,warmShaders,cosmosShaders}.ts``), particles carried by a flow,
 * tsParticles, a wireframe landscape — the last three are Portalab's renderers. Its element gets the shader in
 * its folder (``render: {kind: "glsl", file}``, the same contract as an imported pack's ambience) or, without
 * one, the renderer (``render: {kind: "renderer", renderer: "layers"}``), the layers and the CSS ambience
 * standing in for it in ``render.params`` (``flow``, ``particles``, ``mesh``, ``fallback``; ``common: "safe"``
 * for a shader written after the noise safe on phones). « Live weather »
 * (``weathersky``) stays Portalab's own renderer: it is drawn from the weather report's numbers.
 *
 *   node scripts/extract-builtin-ambients.mjs [--dry-run]
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
const KEPT = new Set(["weathersky"]);

const scratch = mkdtempSync(join(tmpdir(), "portalab-ambients-"));
const entry = join(scratch, "entry.ts");
writeFileSync(
  entry,
  [
    `export { LAYERS, PREMIUM_FALLBACK } from ${JSON.stringify(join(PREMIUM, "PremiumAmbient"))};`,
    `export { SHADERS, COMMON } from ${JSON.stringify(join(PREMIUM, "shaders"))};`,
    `export { COZY_SHADERS } from ${JSON.stringify(join(PREMIUM, "cozyShaders"))};`,
    `export { SAFE_COMMON } from ${JSON.stringify(join(PREMIUM, "weatherShader"))};`,
    `export { WARM_SHADERS } from ${JSON.stringify(join(PREMIUM, "warmShaders"))};`,
    `export { COSMOS_SHADERS } from ${JSON.stringify(join(PREMIUM, "cosmosShaders"))};`,
  ].join("\n"),
);
execFileSync(join(FRONT, "node_modules", ".bin", "esbuild"), [
  entry,
  "--bundle",
  "--format=esm",
  "--platform=node",
  "--log-level=error",
  "--jsx=automatic",
  `--outfile=${join(scratch, "ambients.mjs")}`,
]);
const m = await import(pathToFileURL(join(scratch, "ambients.mjs")).href);
rmSync(scratch, { recursive: true, force: true });
const shaderOf = (name) =>
  m.SHADERS[name] ?? m.COZY_SHADERS[name] ?? m.WARM_SHADERS[name] ?? m.COSMOS_SHADERS[name];

const found = new Set();
let written = 0;
for (const pack of readdirSync(PACKS)) {
  const elements = join(PACKS, pack, "elements");
  if (!existsSync(elements)) continue;
  for (const folder of readdirSync(elements)) {
    const file = join(elements, folder, "element.json");
    const element = JSON.parse(readFileSync(file, "utf8"));
    const layers = element.type === "ambient" && !KEPT.has(element.look) ? m.LAYERS[element.look] : undefined;
    if (!layers) continue;
    found.add(element.look);
    const params = {
      ...(layers.flow ? { flow: Array.isArray(layers.flow) ? layers.flow : [layers.flow] } : {}),
      ...(layers.particles ? { particles: layers.particles } : {}),
      ...(layers.mesh ? { mesh: true } : {}),
      ...(m.PREMIUM_FALLBACK[element.look] ? { fallback: m.PREMIUM_FALLBACK[element.look] } : {}),
    };
    const css = element.render?.kind === "css" ? (element.render.css ?? []) : [];
    let shader = null;
    if (layers.shader) {
      const source = shaderOf(layers.shader);
      // after the shared noise, or its variant safe on phones of lower precision (``common: "safe"``)
      if (source?.startsWith(m.SAFE_COMMON)) {
        shader = source.slice(m.SAFE_COMMON.length);
        params.common = "safe";
      } else if (source?.startsWith(m.COMMON)) shader = source.slice(m.COMMON.length);
      else throw new Error(`${element.look}: no shader « ${layers.shader} » after COMMON`);
    }
    element.render = shader
      ? { kind: "glsl", file: `${layers.shader}.glsl`, ...(css.length ? { css } : {}), params }
      : { kind: "renderer", renderer: "layers", ...(css.length ? { css } : {}), params };
    written += 1;
    if (dry) continue;
    if (shader)
      writeFileSync(
        join(elements, folder, `${layers.shader}.glsl`),
        `// Portalab — ambient/${element.look}: the « ${layers.shader} » ambience (spec 028, B2)\n${shader.replace(/^\n/, "")}`,
      );
    writeFileSync(file, `${JSON.stringify(element, null, 2)}\n`);
  }
}
const missing = Object.keys(m.LAYERS).filter((look) => !KEPT.has(look) && !found.has(look));
console.log(JSON.stringify({ written, missing }, null, 1));
