/**
 * UI preferences (spec 022 data model): user-tier ``ui.*`` settings stored by Administration (020) and
 * mirrored to localStorage for first paint. Policy (allowed themes, text-scale bounds, forced reduced
 * motion) constrains the *effective* value while the stored preference is retained (CD-011).
 */

/** 027: the universe themes (built in, most of them sold in the shop). */
export const UNIVERSE_THEMES = [
  "wizard",
  "galaxy",
  "matrix",
  "desert",
  "horror",
  "halloween",
  "christmas",
  "comic",
  "manga",
  "cartoon",
  "cozy",
  "futuristic",
  "minimal",
  "alien",
  "heroes",
  "neowave",
  "disco",
  "cyberpunk",
  "sincity",
  "plex",
  "upsidedown",
  "middleearth",
  "vhs",
  "nova",
  "nostromo",
  // issue 130: the cosmos
  "observatory",
  "spacestation",
  "starship",
] as const;

/** issue 1: the form of an imported look's key (the server checks it exists). */
const IMPORTED_LOOK = /^[a-z0-9][a-z0-9_.-]{0,63}$/;
/** 030: a kind of visual a plugin adds (``plugin:<plugin>.<kind>``). */
const PLUGIN_KIND = /^plugin:[a-z][a-z0-9_-]{0,63}\.[a-z][a-z0-9_-]{0,63}$/;

export type Density = "compact" | "comfortable" | "spacious";
export type ReducedMotion = "system" | "on" | "off";

/** 027: accent colours over the theme — ``theme``, or a pack's palette (028: none is written here). */
export type PaletteKey = string;
export type LevelUpLook = string;
// 028: the looks are the visual packs' (``visuals/vocabulary``): none is listed in the interface's code
export type Ambient = string;
export type CelebrationKey = string;
export type NotificationStyle = string;
export type NotificationAnimation = string;

export interface UiPreferences {
  theme: string | null;
  density: Density;
  textScale: number;
  contrast: "default" | "high";
  reducedMotion: ReducedMotion;
  /** #29: decorative animations — all, discreet (fewer at once, slower: saves battery) or none. */
  animations: "all" | "discreet" | "none";
  soundEnabled: boolean;
  notificationPosition: "top-end" | "top-start" | "bottom-end" | "bottom-start";
  notificationDurationSeconds: number;
  notificationStyle: NotificationStyle | "theme";
  /** 027: how notifications come in (some animations are sold in the shop); ``theme``: the theme's. */
  notificationAnimation: NotificationAnimation | "theme";
  /** 027: animated layer behind the portal — ``theme`` (the theme's), none, or one bought in the shop. */
  ambient: Ambient | "theme";
  /** 027: celebration effect for rewards — ``theme`` (the theme's) or one bought in the shop. */
  celebration: CelebrationKey | "theme";
  /** 027: accent colours over the theme (some are sold in the shop). */
  palette: PaletteKey;
  /** 027: how a level-up is shown — ``theme`` (the theme's own) or one bought in the shop. */
  levelUp: LevelUpLook | "theme";
  campaignThemes: "allow" | "ignore";
  /** Light/dark choice for theme families (027 R8): dark by default, or follow the device. */
  colorMode: "dark" | "light" | "system";
  /** 030: the look chosen for each kind of visual a plugin adds (``plugin:<key>.<kind>`` → look). */
  pluginLooks: Record<string, string>;
  /** Issue 229: the actor's own portrait in a round badge by their character's image, on the media cards. */
  cardActorBadge: boolean;
}

export interface UiPolicy {
  allowedThemes: string[];
  defaultTheme: string;
  textScaleMin: number;
  textScaleMax: number;
  forceReducedMotion: boolean;
}

export const DEFAULT_PREFERENCES: UiPreferences = {
  theme: null,
  density: "comfortable",
  textScale: 1,
  contrast: "default",
  reducedMotion: "system",
  animations: "all",
  soundEnabled: true,
  notificationPosition: "top-end",
  notificationDurationSeconds: 6,
  notificationStyle: "theme",
  notificationAnimation: "theme",
  ambient: "theme",
  celebration: "theme",
  palette: "theme",
  levelUp: "theme",
  campaignThemes: "allow",
  colorMode: "dark",
  pluginLooks: {},
  cardActorBadge: true,
};

export const DEFAULT_POLICY: UiPolicy = {
  allowedThemes: [
    "portalab-dark",
    "portalab-light",
    "orbit",
    "studio",
    "light",
    "dark",
    "high-contrast",
    ...UNIVERSE_THEMES,
  ],
  defaultTheme: "portalab",
  textScaleMin: 0.85,
  textScaleMax: 2,
  forceReducedMotion: false,
};

/** ``ui.<name>`` setting keys of each preference field (declared by the backend ``ui`` module). */
export const PREFERENCE_KEYS: Record<keyof UiPreferences, string> = {
  theme: "ui.theme",
  density: "ui.density",
  textScale: "ui.textScale",
  contrast: "ui.contrast",
  reducedMotion: "ui.reducedMotion",
  animations: "ui.animations",
  soundEnabled: "ui.soundEnabled",
  notificationPosition: "ui.notificationPosition",
  notificationDurationSeconds: "ui.notificationDurationSeconds",
  notificationStyle: "ui.notificationStyle",
  notificationAnimation: "ui.notificationAnimation",
  ambient: "ui.ambient",
  celebration: "ui.celebration",
  palette: "ui.palette",
  levelUp: "ui.levelUp",
  campaignThemes: "ui.campaignThemes",
  colorMode: "ui.colorMode",
  pluginLooks: "ui.pluginLooks",
  cardActorBadge: "ui.cardActorBadge",
};

/** Accept only known fields with valid values (an option removed by an update falls back to its default). */
export function sanitize(input: object): UiPreferences {
  const raw = input as Record<string, unknown>;
  const out: UiPreferences = { ...DEFAULT_PREFERENCES };
  const pick = <K extends keyof UiPreferences>(key: K, allowed: readonly unknown[]) => {
    if (allowed.includes(raw[key])) {
      out[key] = raw[key] as UiPreferences[K];
    }
  };
  if (typeof raw.theme === "string" || raw.theme === null) out.theme = raw.theme ?? null;
  pick("density", ["compact", "comfortable", "spacious"]);
  pick("contrast", ["default", "high"]);
  pick("reducedMotion", ["system", "on", "off"]);
  pick("animations", ["all", "discreet", "none"]);
  pick("notificationPosition", ["top-end", "top-start", "bottom-end", "bottom-start"]);
  // 028: a look is a pack's (Portalab's own included) — any well-formed key the server accepted
  const pickLook = <K extends keyof UiPreferences>(key: K) => {
    const value = raw[key];
    if (value === "theme" || (typeof value === "string" && IMPORTED_LOOK.test(value))) {
      out[key] = value as UiPreferences[K];
    }
  };
  pickLook("notificationStyle");
  pickLook("notificationAnimation");
  pickLook("ambient");
  pickLook("celebration");
  pickLook("palette");
  pickLook("levelUp");
  pick("campaignThemes", ["allow", "ignore"]);
  pick("colorMode", ["dark", "light", "system"]);
  if (raw.pluginLooks && typeof raw.pluginLooks === "object" && !Array.isArray(raw.pluginLooks)) {
    out.pluginLooks = Object.fromEntries(
      Object.entries(raw.pluginLooks as Record<string, unknown>).filter(
        (entry): entry is [string, string] =>
          PLUGIN_KIND.test(entry[0]) && typeof entry[1] === "string" && IMPORTED_LOOK.test(entry[1]),
      ),
    );
  }
  if (typeof raw.soundEnabled === "boolean") out.soundEnabled = raw.soundEnabled;
  if (typeof raw.cardActorBadge === "boolean") out.cardActorBadge = raw.cardActorBadge;
  if (typeof raw.textScale === "number" && Number.isFinite(raw.textScale)) out.textScale = raw.textScale;
  if (typeof raw.notificationDurationSeconds === "number") {
    out.notificationDurationSeconds = Math.min(60, Math.max(2, Math.round(raw.notificationDurationSeconds)));
  }
  return out;
}
