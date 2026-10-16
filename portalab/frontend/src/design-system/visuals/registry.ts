import { useSyncExternalStore } from "react";
import { parseTheme, type ThemeDefinition } from "../themes/schema";
import { guardedSheet } from "./cssGuard";

/**
 * 028 (from the POC of issue 1): the looks of visual packs — their animations in their own files, loaded at run
 * time, never in Portalab's code. Each element is drawn by its kind:
 *
 * - ``css``: its stylesheets are read, guarded (``cssGuard``: a look styles its own element only, an interface
 *   never a protected surface) and adopted by the document; they style the interface's hooks (``data-frame``,
 *   ``data-name``, ``data-look``, ``data-effect``…) like the built-in looks;
 * - ``glsl``: its fragment is registered with the GPU looks (``badgeFx``: a shape or a whole stage, same
 *   contract as the built-in effects) or, for an ambience, run as a full-screen shader after ``COMMON``;
 * - ``js``: its module runs in a sandbox (``sandbox.ts``: an iframe of an opaque origin — no account, no
 *   network, no page of Portalab's), never in this page;
 * - ``theme``: an interface — its definition is served by the interfaces' registry, its stylesheets linked;
 * - ``renderer``: a renderer of Portalab's own, with the element's parameters (particles, weather…);
 * - ``data``: packs, boosters, palettes (their colours come with the element), titles and badges.
 *
 * Two scopes: ``live`` (the published packs switched on, for everyone) and ``preview`` (a version shown in the
 * administration's sandbox before it is validated — it wins over ``live`` while the sandbox is open).
 */

export type ExternalKind = "css" | "glsl" | "js" | "theme" | "renderer" | "data" | "none";
export type Scope = "live" | "preview" | "scene";

export interface NavPlace {
  position: "top" | "bottom" | "left" | "right" | "floating";
  size: number;
  expands: boolean;
}

export interface ExternalElement {
  pack: string;
  sha: string;
  /** the shop product (absent for what is never sold: navigations, scene parts) */
  product: string;
  type: string;
  look: string | null;
  kind: ExternalKind;
  names: Record<string, string>;
  file: string | null;
  css: string[];
  stage: boolean;
  shape: number;
  radius: string | null;
  reveal: number | null;
  duration: number | null;
  palette: Record<string, Record<string, string>> | null;
  preview: string | null;
  nav?: NavPlace | null;
  renderer?: string | null;
  params?: Record<string, unknown> | null;
  rarity?: string | null;
  parts?: Record<string, unknown> | null;
  contracts?: string[] | null;
}

/** An element as the API sends it (empty fields left out), completed. */
export function normaliseElement(
  raw: Partial<ExternalElement> & { pack: string; type: string },
): ExternalElement {
  return {
    sha: "",
    look: null,
    kind: "data",
    names: {},
    file: null,
    stage: false,
    shape: 0,
    radius: null,
    reveal: null,
    duration: null,
    palette: null,
    preview: null,
    ...raw,
    product: raw.product ?? `${raw.type}:${raw.look ?? ""}`,
    css: raw.css ?? [],
  };
}

/** A GLSL look registered with the GPU renderer. */
export interface ExternalFx {
  body: string;
  stage: boolean;
  ambient: boolean;
}

const scopes: Record<Scope, Map<string, ExternalElement>> = {
  live: new Map(),
  preview: new Map(),
  scene: new Map(),
};
const shaders = new Map<string, ExternalFx>();
// the definitions of imported interfaces (element ``theme``), by key, parsed
const interfaces = new Map<string, ThemeDefinition>();
const listeners = new Set<() => void>();
let revision = 0;

const keyOf = (type: string, look: string) => `${type}:${look}`;

function notify() {
  revision += 1;
  for (const listener of listeners) listener();
}

/** The name an external GLSL look is registered under (its fingerprint in it: a new version recompiles). */
export function fxName(element: Pick<ExternalElement, "pack" | "sha" | "look" | "type">): string {
  // 028: its type too — two elements of one pack may share a look's key (a scene's background and its
  // booster's look, both « maree »): each keeps its own shader
  return `ext:${element.pack}.${element.sha}:${element.type}:${element.look}`;
}

export function externalFx(name: string): ExternalFx | undefined {
  return shaders.get(name);
}

/** The element drawing ``look`` of ``type`` (the sandbox's version first), if a pack brings it. */
export function externalLook(type: string, look: string | null | undefined): ExternalElement | undefined {
  if (!look) return undefined;
  const key = keyOf(type, look);
  return scopes.preview.get(key) ?? scopes.scene.get(key) ?? scopes.live.get(key);
}

export function externalLooks(type: string): ExternalElement[] {
  const out = new Map<string, ExternalElement>();
  for (const scope of ["live", "preview"] as const) {
    for (const element of scopes[scope].values())
      if (element.type === type && element.look) out.set(element.look, element);
  }
  return [...out.values()];
}

/** Re-renders when packs are installed or removed. */
export function useExternalRevision(): number {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => revision,
    () => revision,
  );
}

// the packs' stylesheets, guarded (``cssGuard``) and adopted by the document — never linked as they are
const sheets: Record<Scope, CSSStyleSheet[]> = { live: [], preview: [], scene: [] };

function adopt() {
  if (typeof document === "undefined" || !("adoptedStyleSheets" in document)) return;
  const ours = new Set([...sheets.live, ...sheets.preview, ...sheets.scene]);
  const others = document.adoptedStyleSheets.filter((sheet) => !ours.has(sheet) && !retired.has(sheet));
  document.adoptedStyleSheets = [...others, ...sheets.live, ...sheets.scene, ...sheets.preview];
  retired.clear();
}
const retired = new Set<CSSStyleSheet>();

async function text(url: string): Promise<string | null> {
  try {
    const response = await fetch(url, { credentials: "same-origin" });
    return response.ok ? await response.text() : null;
  } catch {
    return null;
  }
}

/** Installs a list of elements in a scope (replacing what that scope held): stylesheets, GPU looks. */
export async function installElements(raw: ExternalElement[], scope: Scope): Promise<void> {
  uninstallScope(scope, false);
  const list = raw.map(normaliseElement);
  const next = new Map<string, ExternalElement>();
  const built: CSSStyleSheet[] = [];
  await Promise.all(
    list.map(async (element) => {
      for (const url of element.css) {
        const css = await text(url);
        const sheet = css === null ? null : guardedSheet(css, url, element);
        if (sheet) built.push(sheet);
      }
      if (element.kind === "glsl" && element.file) {
        const body = await text(element.file);
        if (body !== null) {
          const ambient = element.type === "ambient" || element.type === "profile_background";
          shaders.set(fxName(element), { body, stage: element.stage, ambient });
        }
      }
      if (element.kind === "theme" && element.file && element.look) {
        const raw = await text(element.file);
        const parsed = raw ? parseTheme(JSON.parse(raw)).theme : undefined;
        if (parsed) interfaces.set(element.look, parsed);
      }
      if (element.look) next.set(keyOf(element.type, element.look), element);
    }),
  );
  scopes[scope] = next;
  sheets[scope] = built;
  adopt();
  notify();
}

export function uninstallScope(scope: Scope, announce = true): void {
  for (const sheet of sheets[scope]) retired.add(sheet);
  sheets[scope] = [];
  adopt();
  scopes[scope] = new Map();
  if (announce) notify();
}

/** An imported interface's definition (to preview or try it before it is published). */
export function externalTheme(key: string | null | undefined): ThemeDefinition | undefined {
  return key && externalLook("theme", key) ? interfaces.get(key) : undefined;
}

// the catalog key naming each type's looks (the interface's pickers read their names there)
const NAME_KEYS: Record<string, string> = {
  level_up: "notifications:levelUp.names",
  effect: "notifications:universe.celebrations",
  ambient: "notifications:universe.ambients",
  profile_background: "notifications:universe.ambients",
  avatar_frame: "community:looks.frame",
  profile_banner: "community:looks.banner",
  name_style: "community:looks.name",
  level_badge: "notifications:levelBadge.names",
  notification_style: "notifications:looks.styles",
  notification_animation: "notifications:looks.animations",
  palette: "notifications:palette.names",
};

/** The names the packs give their looks, as catalog messages for ``language`` (merged over the catalogs). */
export function externalMessages(language: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const scope of ["live", "preview"] as const) {
    for (const element of scopes[scope].values()) {
      const prefix = NAME_KEYS[element.type];
      const name = element.names[language.split("-")[0] ?? "en"] || element.names.en || element.names.fr;
      if (prefix && element.look && name) out[`${prefix}.${element.look}`] = name;
    }
  }
  return out;
}

/** The colours of a pack's palette (its contrast colour, when it gives one). */
export function externalPalette(
  look: string,
  scheme: "dark" | "light",
): { accent: string; accentAlt: string; contrast: string | null } | null {
  const colours = externalLook("palette", look)?.palette?.[scheme];
  if (!colours?.accent || !colours.accentAlt) return null;
  return { accent: colours.accent, accentAlt: colours.accentAlt, contrast: colours.contrast ?? null };
}

// --- 028: Portalab's own looks whose pack the administrator switched off ---------------------------------
// They are drawn by the interface's own code, so it must be told: whoever wears one sees the default instead
// (their choice is kept, and comes back when the pack does).
let withheld = new Map<string, Set<string>>();

export function setWithheld(byType: Record<string, string[]> | undefined): void {
  const next = new Map(Object.entries(byType ?? {}).map(([type, looks]) => [type, new Set(looks)]));
  const same =
    next.size === withheld.size &&
    [...next].every(([type, looks]) => {
      const before = withheld.get(type);
      return before?.size === looks.size && [...looks].every((look) => before.has(look));
    });
  if (same) return;
  withheld = next;
  notify();
}

export function isWithheld(type: string, look: string | null | undefined): boolean {
  return Boolean(look && withheld.get(type)?.has(look));
}

/** A look as it shows: the default when its pack is off. */
export function shownLook<T extends string | null | undefined>(type: string, look: T, fallback: T): T {
  return isWithheld(type, look) ? fallback : look;
}
