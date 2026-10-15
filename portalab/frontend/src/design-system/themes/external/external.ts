import { useSyncExternalStore } from "react";
import { parseTheme, type ThemeDefinition } from "../schema";

/**
 * issue 1 (POC): the looks of imported visual packs — their animations in their own files, loaded at run
 * time, never in Portalab's code. Each element is drawn by its kind:
 *
 * - ``css``: its stylesheets are linked into the page; they style the interface's hooks (``data-frame``,
 *   ``data-name``, ``data-look``, ``data-effect``…) like the built-in looks (fonts declared in them, with
 *   addresses relative to the sheet);
 * - ``glsl``: its fragment is registered with the GPU looks (``badgeFx``: a shape or a whole stage, same
 *   contract as the built-in effects) or, for an ambience, run as a full-screen shader after ``COMMON``;
 * - ``js``: its module is imported when the look shows; its default export is called with the element to draw
 *   into and the moment's context, and returns what stops it (the administrator accepted it runs scripts);
 * - ``theme``: an interface — its definition is served by the interfaces' registry, its stylesheets linked;
 * - ``none``: packs, boosters, palettes (their colours come with the element), titles and badges.
 *
 * Two scopes: ``live`` (the published packs switched on, for everyone) and ``preview`` (a version shown in the
 * administration's sandbox before it is validated — it wins over ``live`` while the sandbox is open).
 */

export type ExternalKind = "css" | "glsl" | "js" | "theme" | "none";
export type Scope = "live" | "preview";

export interface ExternalElement {
  pack: string;
  sha: string;
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
}

/** A GLSL look registered with the GPU renderer. */
export interface ExternalFx {
  body: string;
  stage: boolean;
  ambient: boolean;
}

/** What a script look receives when it is mounted. */
export interface ScriptContext {
  type: string;
  look: string;
  /** a level-up's new level, a celebration's text */
  level?: number;
  text?: string;
  reducedMotion: boolean;
  /** the address of one of the element's own files (``assets("spark.png")``) */
  asset: (path: string) => string;
}
type Mount = (
  host: HTMLElement,
  context: ScriptContext,
) => (() => void) | { destroy: () => void } | undefined;

const scopes: Record<Scope, Map<string, ExternalElement>> = { live: new Map(), preview: new Map() };
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
export function fxName(element: Pick<ExternalElement, "pack" | "sha" | "look">): string {
  return `ext:${element.pack}.${element.sha}:${element.look}`;
}

export function externalFx(name: string): ExternalFx | undefined {
  return shaders.get(name);
}

/** The element drawing ``look`` of ``type`` (the sandbox's version first), if a pack brings it. */
export function externalLook(type: string, look: string | null | undefined): ExternalElement | undefined {
  if (!look) return undefined;
  const key = keyOf(type, look);
  return scopes.preview.get(key) ?? scopes.live.get(key);
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

function link(url: string, scope: Scope) {
  if (typeof document === "undefined") return;
  if (document.head.querySelector(`link[data-visual="${scope}"][href="${CSS.escape(url)}"]`)) return;
  const element = document.createElement("link");
  element.rel = "stylesheet";
  element.href = url;
  element.dataset.visual = scope;
  document.head.append(element);
}

async function text(url: string): Promise<string | null> {
  try {
    const response = await fetch(url, { credentials: "same-origin" });
    return response.ok ? await response.text() : null;
  } catch {
    return null;
  }
}

/** Installs a list of elements in a scope (replacing what that scope held): stylesheets, GPU looks. */
export async function installElements(list: ExternalElement[], scope: Scope): Promise<void> {
  uninstallScope(scope, false);
  const next = new Map<string, ExternalElement>();
  await Promise.all(
    list.map(async (element) => {
      for (const sheet of element.css) link(sheet, scope);
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
  notify();
}

export function uninstallScope(scope: Scope, announce = true): void {
  if (typeof document !== "undefined") {
    for (const element of document.head.querySelectorAll(`link[data-visual="${scope}"]`)) element.remove();
  }
  scopes[scope] = new Map();
  if (announce) notify();
}

/** An imported interface's definition (to preview or try it before it is published). */
export function externalTheme(key: string | null | undefined): ThemeDefinition | undefined {
  return key && externalLook("theme", key) ? interfaces.get(key) : undefined;
}

/** Mounts a script look into ``host``; returns what stops it (nothing when it could not start). */
export async function mountScript(
  element: ExternalElement,
  host: HTMLElement,
  context: Omit<ScriptContext, "asset" | "type" | "look">,
): Promise<(() => void) | null> {
  if (!element.file || !element.look) return null;
  try {
    const module = (await import(/* @vite-ignore */ element.file)) as { default?: Mount };
    if (typeof module.default !== "function") return null;
    const base = element.file.slice(0, element.file.lastIndexOf("/") + 1);
    const stop = module.default(host, {
      ...context,
      type: element.type,
      look: element.look,
      asset: (path: string) => base + path.replace(/^\.?\//, ""),
    });
    if (typeof stop === "function") return stop;
    if (stop && typeof stop.destroy === "function") return () => stop.destroy();
    return () => undefined;
  } catch (error) {
    console.warn("visual pack script:", element.product, error);
    return null;
  }
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

/** The colours of an imported palette. */
export function externalPalette(
  look: string,
  scheme: "dark" | "light",
): { accent: string; accentAlt: string; contrast: string } | null {
  const colours = externalLook("palette", look)?.palette?.[scheme];
  if (!colours?.accent || !colours.accentAlt) return null;
  return { accent: colours.accent, accentAlt: colours.accentAlt, contrast: colours.contrast ?? "#ffffff" };
}
