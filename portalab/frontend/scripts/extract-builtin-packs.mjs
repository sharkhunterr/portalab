#!/usr/bin/env node
/**
 * 028 B2 (T036, R8): moves Portalab's own looks out of its stylesheets into their built-in pack elements.
 *
 * For every family below, each rule whose selector starts on the family's hook — `.avatar-frame[data-frame="gold"]`,
 * `.levelup[data-look="nova"]`… — is moved, selector by selector, into `packs/looks/<type>/<look>/look.css`
 * (its `@media`/`@supports` wrappers kept, the keyframes it animates copied along); what stays is Portalab's own:
 * the base rules (the fallbacks every family keeps in the code), and the rules a look's stylesheet may not hold
 * (a sibling, `:has()`, the document's root — reported, to rewrite by hand). Each look's stylesheet is written
 * in its element's folder (`packs/builtin/<pack>/elements/<element>/look.css`), the element then drawn by it
 * (`render: {kind: "css"}`); `backend/scripts/build_builtin_packs.py` keeps these files when it writes the packs
 * again. Only looks a built-in pack holds are moved — never the socle's (the fallbacks).
 *
 *   node scripts/extract-builtin-packs.mjs [--family avatar_frame,…] [--dry-run]
 */
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import postcss from "postcss";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = resolve(HERE, "..", "..");
const SRC = join(APP, "frontend", "src");
const PACKS = join(APP, "packs", "builtin");
const SOCLE = "portalab-socle";

/** each family: its type, the file holding its looks, and its hook (the look's key in the first compound) */
const FAMILIES = [
  {
    type: "avatar_frame",
    file: "design-system/themes/cosmetics.css",
    hook: /^\.avatar-frame\[data-frame="([^"]+)"\]/,
  },
  {
    type: "level_badge",
    file: "design-system/themes/cosmetics.css",
    hook: /^\.ds-level\[data-look="([^"]+)"\]/,
  },
  {
    type: "profile_banner",
    file: "design-system/themes/cosmetics.css",
    hook: /^\.profile-banner\[data-banner="([^"]+)"\]/,
  },
  {
    type: "name_style",
    file: "design-system/themes/cosmetics.css",
    hook: /^\.name-style\[data-name="([^"]+)"\]/,
  },
  {
    type: "title",
    file: "design-system/themes/cosmetics.css",
    hook: /^\.cosmetic-title\[data-style="([^"]+)"\]/,
  },
  {
    type: "badge",
    file: "design-system/themes/cosmetics.css",
    hook: /^\.cosmetic-badge\[data-style="([^"]+)"\]/,
  },
  { type: "level_up", file: "design-system/themes/levelup.css", hook: /^\.levelup\[data-look="([^"]+)"\]/ },
  {
    type: "ambient",
    file: "design-system/themes/ambient.css",
    hook: /^(?:\.ambient(?:--premium)?)?\[data-ambient="([^"]+)"\]/,
  },
  {
    type: "effect",
    file: "design-system/themes/celebration.css",
    hook: /^(?:\.ds-celebration)?\[data-effect="([^"]+)"\]/,
  },
  {
    type: "notification_style",
    file: "design-system/themes/universe.css",
    hook: /^\.ds-notifications(?:--[\w-]+)?\[data-style="([^"]+)"\]/,
  },
  {
    type: "notification_animation",
    file: "design-system/themes/universe.css",
    hook: /^\.ds-notifications\[data-animation="([^"]+)"\]/,
  },
];
// what a look's stylesheet may not hold (the guard's rule): it stays in the code, to rewrite by hand
const ESCAPES = /\+|~(?!=)|:has\(|:root|(?:^|[\s>(,])(?:html|body)\b/i;
const NTH = /:nth-[a-z-]+\(\s*(?:[-+]?\d*n\s*(?:[-+]\s*\d+)?|[-+]?\d+|odd|even)\s*/gi;

const args = process.argv.slice(2);
const dry = args.includes("--dry-run");
const only = args.includes("--family") ? new Set(args[args.indexOf("--family") + 1].split(",")) : null;

/** the looks the built-in packs hold, per type (from their elements): look → its element's folder */
function builtinLooks() {
  const out = new Map();
  for (const pack of readdirSync(PACKS)) {
    // the socle's looks are the fallbacks drawn before any pack is read (sign-in page, first paint): they stay
    if (pack === SOCLE) continue;
    const elements = join(PACKS, pack, "elements");
    if (!existsSync(elements)) continue;
    for (const folder of readdirSync(elements)) {
      const file = join(elements, folder, "element.json");
      if (!existsSync(file)) continue;
      const element = JSON.parse(readFileSync(file, "utf8"));
      if (!element.look) continue;
      if (!out.has(element.type)) out.set(element.type, new Map());
      if (!out.get(element.type).has(element.look))
        out.get(element.type).set(element.look, join(elements, folder));
    }
  }
  return out;
}

/** the first compound of a selector (up to the first combinator outside brackets and parentheses) */
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

/** the arguments of a selector list (commas inside parentheses and brackets respected) */
function splitList(list) {
  const out = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < list.length; i++) {
    const c = list[i];
    if (c === "(" || c === "[") depth++;
    else if (c === ")" || c === "]") depth--;
    else if (c === "," && depth === 0) {
      out.push(list.slice(start, i).trim());
      start = i + 1;
    }
  }
  out.push(list.slice(start).trim());
  return out;
}

/**
 * A selector whose first compound shares rules between looks — ``:is(.cosmetic-badge, .cosmetic-title)[data-style="x"]``,
 * ``.ds-notifications:is([data-style="a"], [data-style="b"]) …`` — as one selector per look; the member's level
 * look once read on the root (``:root[data-level-badge="x"] .ds-level:not([data-look])``) is dropped: the badge
 * wears its look itself now (``data-look``).
 */
function expand(selector) {
  if (/^:root\[data-level-badge="[^"]+"\]/.test(selector)) return [];
  const compound = firstCompound(selector);
  const at = compound.indexOf(":is(");
  if (at < 0) return [selector];
  let depth = 0;
  let end = at + 3;
  for (; end < selector.length; end++) {
    if (selector[end] === "(") depth++;
    else if (selector[end] === ")" && --depth === 0) break;
  }
  const head = selector.slice(0, at);
  const tail = selector.slice(end + 1);
  return splitList(selector.slice(at + 4, end)).flatMap((arg) => expand(`${head}${arg}${tail}`));
}

/** the at-rules wrapping a node (outermost first), as text to reopen them around the moved rule */
function wrappers(node) {
  const out = [];
  for (let parent = node.parent; parent && parent.type !== "root"; parent = parent.parent) {
    if (parent.type === "atrule") out.unshift(`@${parent.name} ${parent.params}`);
  }
  return out;
}

const ANIMATION = /\banimation(?:-name)?\s*:/i;
function animationNames(rule) {
  const names = new Set();
  rule.walkDecls((decl) => {
    if (!ANIMATION.test(`${decl.prop}:`)) return;
    for (const part of decl.value.split(",")) {
      for (const word of part.trim().split(/\s+/)) {
        if (/^[a-z_][\w-]*$/i.test(word) && !KEYWORDS.has(word)) names.add(word);
      }
    }
  });
  return names;
}
const KEYWORDS = new Set([
  "none",
  "infinite",
  "linear",
  "ease",
  "ease-in",
  "ease-out",
  "ease-in-out",
  "alternate",
  "alternate-reverse",
  "reverse",
  "normal",
  "forwards",
  "backwards",
  "both",
  "running",
  "paused",
  "step-start",
  "step-end",
  "initial",
  "inherit",
  "unset",
]); // prettier-ignore

const looks = builtinLooks();
const families = FAMILIES.filter((f) => !only || only.has(f.type));
const byFile = new Map();
for (const family of families) {
  if (!byFile.has(family.file)) byFile.set(family.file, []);
  byFile.get(family.file).push(family);
}

// every keyframes of the theme stylesheets, by name (a look may animate one defined elsewhere)
const keyframes = new Map();
for (const file of new Set(FAMILIES.map((f) => f.file))) {
  postcss.parse(readFileSync(join(SRC, file), "utf8")).walkAtRules(/keyframes$/i, (rule) => {
    keyframes.set(rule.params.trim(), rule.toString());
  });
}

const report = { moved: {}, kept: [], unknown: {} };
const sheets = new Map(); // "type/look" → [ { wrappers, text } ], animations
for (const [file, list] of byFile) {
  const path = join(SRC, file);
  const root = postcss.parse(readFileSync(path, "utf8"));
  root.walkRules((rule) => {
    if (rule.parent?.type === "atrule" && /keyframes$/i.test(rule.parent.name)) return;
    const stay = [];
    const expanded = rule.selectors.flatMap((selector) => {
      const parts = expand(selector.trim());
      const hooked = parts.some((part) => list.some((family) => family.hook.test(firstCompound(part))));
      return hooked || !parts.length ? parts : [selector];
    });
    for (const selector of expanded) {
      const compound = firstCompound(selector.trim());
      let placed = false;
      for (const family of list) {
        const match = family.hook.exec(compound);
        if (!match) continue;
        const look = match[1];
        if (!looks.get(family.type)?.has(look)) {
          report.unknown[family.type] = (report.unknown[family.type] ?? 0) + 1;
          break;
        }
        if (ESCAPES.test(selector.replace(NTH, ":nth("))) {
          report.kept.push(`${family.type}/${look}: ${selector.trim().slice(0, 90)}`);
          break;
        }
        const key = `${family.type}/${look}`;
        if (!sheets.has(key)) sheets.set(key, { parts: [], animations: new Set() });
        const sheet = sheets.get(key);
        const copy = rule.clone({ selectors: [selector.trim()] });
        sheet.parts.push({ wrappers: wrappers(rule), text: copy.toString() });
        for (const name of animationNames(rule)) sheet.animations.add(name);
        report.moved[family.type] = (report.moved[family.type] ?? 0) + 1;
        placed = true;
        break;
      }
      if (!placed) stay.push(selector);
    }
    if (stay.length === rule.selectors.length && stay.every((s, i) => s === rule.selectors[i])) return;
    if (stay.length) rule.selectors = stay;
    else {
      const parent = rule.parent;
      rule.remove();
      // an at-rule left empty goes too
      for (let at = parent; at && at.type === "atrule" && !at.nodes?.length; ) {
        const up = at.parent;
        at.remove();
        at = up;
      }
    }
  });
  if (!dry) writeFileSync(path, root.toString());
}

// each look's stylesheet: its rules in their wrappers, then the keyframes they animate
for (const [key, sheet] of sheets) {
  const lines = [`/* Portalab — ${key}: moved from Portalab's stylesheets (spec 028, B2) */`];
  for (const part of sheet.parts) {
    let text = part.text;
    for (const wrapper of [...part.wrappers].reverse()) text = `${wrapper} {\n${text}\n}`;
    lines.push(text);
  }
  for (const name of sheet.animations) if (keyframes.has(name)) lines.push(keyframes.get(name));
  const [type, look] = key.split("/");
  const folder = looks.get(type).get(look);
  if (!dry) {
    writeFileSync(join(folder, "look.css"), `${lines.join("\n\n")}\n`);
    const file = join(folder, "element.json");
    const element = JSON.parse(readFileSync(file, "utf8"));
    element.render = { kind: "css", css: ["look.css"] };
    writeFileSync(file, `${JSON.stringify(element, null, 2)}\n`);
  }
}

console.log(
  JSON.stringify(
    { sheets: sheets.size, moved: report.moved, unknown: report.unknown, kept: report.kept.length },
    null,
    1,
  ),
);
if (report.kept.length) console.log(`kept in the code (to rewrite by hand):\n  ${report.kept.join("\n  ")}`);
