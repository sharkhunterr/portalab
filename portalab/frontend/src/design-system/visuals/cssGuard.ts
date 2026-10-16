/**
 * issue 1: what an imported pack's stylesheet may style — enforced in the browser, on the browser's own
 * reading of the sheet (its CSS object model), whatever the analysis said:
 *
 * - a **look** styles its own element only: each selector starts on its hook (``[data-…="<look>"]``) and goes
 *   no further than inside it — no sibling (``~``, ``+``), no ``:has()``, never the document's root;
 * - an **interface** styles the whole interface under its own key (``[data-theme="<key>"] …``), never a
 *   protected surface: each selector is made to skip ``[data-protected]`` and what is inside it (the
 *   administration, purchases, confirmations);
 * - addresses: the pack's own files (made absolute) and ``data:`` only; ``@import`` never (a constructed sheet
 *   refuses it); nested rules dropped;
 * - names (028): a pack's ``@keyframes`` get a suffix of their own (no pack can redefine another's animation or
 *   Portalab's), and a ``@font-face`` may not take the name of one of Portalab's own fonts.
 */

const ESCAPES = /[~+]|:has\(|:root|(?:^|[\s>(,])(?:html|body)\b/i;
const PSEUDO_ELEMENT =
  /(::?(?:before|after|first-line|first-letter|placeholder|marker|selection|backdrop|file-selector-button)|::[\w-]+(?:\([^)]*\))?)$/i;
const PROTECTED = ":not([data-protected]):not([data-protected] *)";

function step(char: string): number {
  return char === "(" || char === "[" ? 1 : char === ")" || char === "]" ? -1 : 0;
}

/** The selectors of a list, alone (commas inside parentheses and brackets respected). */
export function splitSelectors(list: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let start = 0;
  for (let index = 0; index < list.length; index++) {
    const char = list[index] as string;
    depth += step(char);
    if (char === "," && depth === 0) {
      out.push(list.slice(start, index).trim());
      start = index + 1;
    }
  }
  out.push(list.slice(start).trim());
  return out.filter(Boolean);
}

function firstCompound(selector: string): string {
  let depth = 0;
  for (let index = 0; index < selector.length; index++) {
    const char = selector[index] as string;
    depth += step(char);
    if (depth === 0 && (/\s/.test(char) || char === ">" || char === "~" || char === "+")) {
      return selector.slice(0, index);
    }
  }
  return selector;
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function lookSelectorOk(selector: string, look: string): boolean {
  const value = escapeRegExp(look);
  const hook = new RegExp(`\\[data-[\\w-]+=(?:"${value}"|'${value}'|${value})\\]`);
  return hook.test(firstCompound(selector)) && !ESCAPES.test(selector);
}

export function interfaceSelectorOk(selector: string, key: string): boolean {
  const value = escapeRegExp(key);
  return new RegExp(`^(?::root|html)?\\[data-theme=(?:"${value}"|'${value}')\\]$`).test(
    firstCompound(selector),
  );
}

/** An interface's selector made to skip protected surfaces (before its pseudo-element, if any). */
export function shieldSelector(selector: string): string {
  const pseudo = selector.match(PSEUDO_ELEMENT);
  if (!pseudo) return `${selector}${PROTECTED}`;
  const at = selector.length - pseudo[0].length;
  return `${selector.slice(0, at)}${PROTECTED}${selector.slice(at)}`;
}

/** Addresses in a sheet: the pack's own files made absolute (against the sheet's address), ``data:`` kept,
 * anything else emptied. */
/** Portalab's own font families: a pack may not declare a face under one of these names. */
const PORTAL_FONTS =
  /^(inter|inter variable|plus jakarta sans|plus jakarta sans variable|system-ui|sans-serif|serif|monospace)$/i;

/** A suffix naming one element's animations apart from everyone else's. */
export function animationSuffix(owner: { pack?: string; look: string | null; type: string }): string {
  return `--${`${owner.pack ?? "pack"}-${owner.type}-${owner.look ?? "x"}`.replace(/[^a-z0-9-]/gi, "-")}`;
}

/** The sheet's ``@keyframes`` renamed with ``suffix``, and the ``animation``/``animation-name`` declarations
 * naming them rewritten to match. */
export function namespaceAnimations(text: string, suffix: string): string {
  const names = new Set<string>();
  for (const match of text.matchAll(/@(?:-webkit-)?keyframes\s+(-?[_a-zA-Z][\w-]*)/g))
    names.add(match[1] as string);
  if (!names.size) return text;
  const renamed = text.replace(
    /(@(?:-webkit-)?keyframes\s+)(-?[_a-zA-Z][\w-]*)/g,
    (_m, head: string, name: string) => `${head}${name}${suffix}`,
  );
  return renamed.replace(/(animation(?:-name)?\s*:)([^;}]*)/gi, (_m, head: string, value: string) => {
    const rewritten = value.replace(/-?[_a-zA-Z][\w-]*/g, (word) =>
      names.has(word) ? `${word}${suffix}` : word,
    );
    return `${head}${rewritten}`;
  });
}

function fontFamilyOf(rule: CSSFontFaceRule): string {
  return rule.style
    .getPropertyValue("font-family")
    .trim()
    .replace(/^["']|["']$/g, "");
}

export function rewriteUrls(text: string, sheetUrl: string): string {
  const base = new URL(sheetUrl, window.location.origin);
  const packRoot = base.href.slice(0, base.href.indexOf("/", base.href.indexOf("/visuals/files/") + 15) + 1);
  return text.replace(/url\(\s*(['"]?)([^'")]*)\1\s*\)/gi, (_match, _quote, raw: string) => {
    const address = raw.trim();
    if (/^data:(image|font)\//i.test(address)) return `url("${address}")`;
    if (/^[a-z][a-z0-9+.-]*:|^\/\//i.test(address)) return 'url("")';
    const resolved = new URL(address, base);
    return resolved.origin === window.location.origin && resolved.href.startsWith(packRoot)
      ? `url("${resolved.href}")`
      : 'url("")';
  });
}

interface RuleParent {
  cssRules: CSSRuleList;
  deleteRule: (index: number) => void;
}

/** Keeps, in place, only what the selector check allows (rewritten when asked); returns how many were cut. */
export function guardRules(
  parent: RuleParent,
  allowed: (selector: string) => boolean,
  rewrite = (s: string) => s,
) {
  let cut = 0;
  for (let index = parent.cssRules.length - 1; index >= 0; index--) {
    const rule = parent.cssRules[index] as CSSRule;
    if (typeof CSSStyleRule !== "undefined" && rule instanceof CSSStyleRule) {
      const nested = (rule as CSSStyleRule & { cssRules?: CSSRuleList }).cssRules;
      if (nested?.length) {
        const host = rule as unknown as RuleParent;
        while (host.cssRules.length) host.deleteRule(0);
        cut += 1;
      }
      const selectors = splitSelectors(rule.selectorText);
      const kept = selectors.filter(allowed);
      cut += selectors.length - kept.length;
      if (!kept.length) parent.deleteRule(index);
      else rule.selectorText = kept.map(rewrite).join(", ");
    } else if ("cssRules" in rule && "deleteRule" in rule && !(rule instanceof CSSKeyframesRule)) {
      cut += guardRules(rule as unknown as RuleParent, allowed, rewrite); // @media, @supports, @container…
    } else if (typeof CSSFontFaceRule !== "undefined" && rule instanceof CSSFontFaceRule) {
      if (PORTAL_FONTS.test(fontFamilyOf(rule))) {
        parent.deleteRule(index); // a face passing itself off as one of Portalab's fonts
        cut += 1;
      }
    } else if (!(rule instanceof CSSKeyframesRule)) {
      parent.deleteRule(index); // anything else (@page, @namespace…)
      cut += 1;
    }
  }
  return cut;
}

/** A pack's stylesheet, guarded: ``null`` when the browser cannot build one. */
export function guardedSheet(
  text: string,
  sheetUrl: string,
  owner: { type: string; look: string | null; pack?: string },
): CSSStyleSheet | null {
  if (typeof CSSStyleSheet === "undefined" || !owner.look) return null;
  const look = owner.look;
  try {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(namespaceAnimations(rewriteUrls(text, sheetUrl), animationSuffix(owner)));
    const cut =
      owner.type === "theme"
        ? guardRules(sheet, (s) => interfaceSelectorOk(s, look), shieldSelector)
        : guardRules(sheet, (s) => lookSelectorOk(s, look));
    if (cut)
      console.warn(`visual pack: ${cut} rule(s) of ${owner.type} « ${look} » left out (outside its scope)`);
    return sheet;
  } catch {
    return null;
  }
}
