#!/usr/bin/env node
/**
 * 028 B2 (T036, T043, R8): moves Portalab's own interfaces into their built-in pack elements, as their looks
 * went: each element gets its definition (``theme.json``, from ``backend/…/ui/themes/builtin/``) and the rules
 * of the interface's stylesheets written for it — every selector starting on ``:root[data-theme="<key>"]``
 * (``design-system/themes/universe.css``, ``features/media/player/player.css``), split selector by selector,
 * their ``@media`` kept and the keyframes they animate copied — in ``theme.css``; it is then drawn as an
 * imported pack's interface (``render: {kind: "theme", file: "theme.json", css: ["theme.css"]}``), its
 * stylesheet guarded the same way (never a protected surface). A rule an interface's stylesheet may not hold
 * stays in the code, reported.
 *
 *   node scripts/extract-builtin-interfaces.mjs [--dry-run]
 *
 * Run once (2026-10-17): what it moved is no longer in the code — the packs are now the interfaces' source,
 * and this script stays as the record of how they were moved.
 */
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import postcss from "postcss";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONT = resolve(HERE, "..");
const APP = resolve(FRONT, "..");
const PACKS = join(APP, "packs", "builtin");
const DEFINITIONS = join(APP, "backend", "src", "portalab", "modules", "ui", "themes", "builtin");
const SHEETS = ["src/design-system/themes/universe.css", "src/features/media/player/player.css"];
const HOOK = /^(?::root|html)?\[data-theme="([^"]+)"\]$/;
const dry = process.argv.includes("--dry-run");

/** the theme elements of the built-in packs: key → folder */
const folders = new Map();
for (const pack of readdirSync(PACKS)) {
  const elements = join(PACKS, pack, "elements");
  if (!existsSync(elements)) continue;
  for (const folder of readdirSync(elements)) {
    const element = JSON.parse(readFileSync(join(elements, folder, "element.json"), "utf8"));
    if (element.type === "theme" && element.look) folders.set(element.look, join(elements, folder));
  }
}

function firstCompound(selector) {
  let depth = 0;
  for (let i = 0; i < selector.length; i++) {
    const c = selector[i];
    if (c === "(" || c === "[") depth++;
    else if (c === ")" || c === "]") depth--;
    else if (depth === 0 && (/\s/.test(c) || c === ">" || c === "+" || c === "~"))
      return selector.slice(0, i);
  }
  return selector;
}
function wrappers(node) {
  const out = [];
  for (let parent = node.parent; parent && parent.type !== "root"; parent = parent.parent)
    if (parent.type === "atrule") out.unshift(`@${parent.name} ${parent.params}`);
  return out;
}
const KEYWORDS = new Set(
  "none infinite linear ease ease-in ease-out ease-in-out alternate alternate-reverse reverse normal forwards backwards both running paused step-start step-end initial inherit unset".split(
    " ",
  ),
);
function animationNames(rule) {
  const names = new Set();
  rule.walkDecls(/^animation(-name)?$/i, (decl) => {
    for (const word of decl.value.replace(/[a-z-]+\([^()]*\)/gi, " ").split(/[\s,]+/))
      if (/^[a-z_][\w-]*$/i.test(word) && !KEYWORDS.has(word)) names.add(word);
  });
  return names;
}

const keyframes = new Map();
for (const file of SHEETS)
  postcss.parse(readFileSync(join(FRONT, file), "utf8")).walkAtRules(/keyframes$/i, (rule) => {
    keyframes.set(rule.params.trim(), rule.toString());
  });

const sheets = new Map(); // key → { parts, animations }
const unknown = new Set();
for (const file of SHEETS) {
  const path = join(FRONT, file);
  const root = postcss.parse(readFileSync(path, "utf8"));
  root.walkRules((rule) => {
    if (rule.parent?.type === "atrule" && /keyframes$/i.test(rule.parent.name)) return;
    const stay = [];
    for (const raw of rule.selectors) {
      const selector = raw.trim();
      const key = HOOK.exec(firstCompound(selector))?.[1];
      if (!key || !folders.has(key)) {
        if (key) unknown.add(key);
        stay.push(raw);
        continue;
      }
      if (!sheets.has(key)) sheets.set(key, { parts: [], animations: new Set() });
      const sheet = sheets.get(key);
      sheet.parts.push({ wrappers: wrappers(rule), text: rule.clone({ selectors: [selector] }).toString() });
      for (const name of animationNames(rule)) sheet.animations.add(name);
    }
    if (stay.length === rule.selectors.length) return;
    if (stay.length) rule.selectors = stay;
    else {
      const parent = rule.parent;
      rule.remove();
      for (let at = parent; at && at.type === "atrule" && !at.nodes?.length; ) {
        const up = at.parent;
        at.remove();
        at = up;
      }
    }
  });
  if (!dry) writeFileSync(path, root.toString());
}

let written = 0;
for (const [key, folder] of folders) {
  const definition = join(DEFINITIONS, `${key}.json`);
  if (!existsSync(definition)) throw new Error(`${key}: no definition`);
  const file = join(folder, "element.json");
  const element = JSON.parse(readFileSync(file, "utf8"));
  const sheet = sheets.get(key);
  element.render = { kind: "theme", file: "theme.json", ...(sheet ? { css: ["theme.css"] } : {}) };
  written += 1;
  if (dry) continue;
  writeFileSync(join(folder, "theme.json"), readFileSync(definition, "utf8"));
  if (sheet) {
    const lines = [
      `/* Portalab — the « ${key} » interface: moved from Portalab's stylesheets (spec 028, B2) */`,
    ];
    for (const part of sheet.parts) {
      let text = part.text;
      for (const wrapper of [...part.wrappers].reverse()) text = `${wrapper} {\n${text}\n}`;
      lines.push(text);
    }
    for (const name of sheet.animations) if (keyframes.has(name)) lines.push(keyframes.get(name));
    writeFileSync(join(folder, "theme.css"), `${lines.join("\n\n")}\n`);
  }
  writeFileSync(file, `${JSON.stringify(element, null, 2)}\n`);
}
console.log(
  JSON.stringify(
    {
      written,
      styled: sheets.size,
      rules: [...sheets.values()].reduce((n, s) => n + s.parts.length, 0),
      unknown: [...unknown],
    },
    null,
    1,
  ),
);
