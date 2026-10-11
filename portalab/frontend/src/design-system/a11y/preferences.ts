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
] as const;

export type Density = "compact" | "comfortable" | "spacious";
export type ReducedMotion = "system" | "on" | "off";

export const PALETTE_KEYS = [
  "theme",
  "ocean",
  "forest",
  "sunset",
  "candy",
  "royal",
  "ember",
  "matrix",
  "aurora",
  "lagoon",
  "lava",
  "mint",
  "gold",
  "ice",
  "rose",
  "toxic",
  "midnight",
  "coffee",
  "lavender",
  "bubblegum",
  // 027: more accent pairs
  "polar",
  "copper",
  "solar",
  "berry",
  "slate",
  "peach",
  "crimson",
  "hawkins",
  "gondor",
  "vhs",
  "nova",
  "nostromo",
] as const;
export type PaletteKey = (typeof PALETTE_KEYS)[number];
/** ``theme``: the theme's own default (027). */
export const NOTIFICATION_STYLES = [
  "toast",
  "banner",
  "pill",
  "minimal",
  "glass",
  "neon",
  "comic",
  "terminal",
  "parchment",
  "hologram",
  "pixel",
  "paper",
  // 027: shapes — a square tile, a round bubble, a thought cloud, a ticket, a luggage tag, two tones
  "square",
  "circle",
  "cloud",
  "ticket",
  "tag",
  "split",
  // 027 universes: space saga, pirates, manga, film noir, VHS tape
  "saga",
  "pirate",
  "manga",
  "noir",
  "vhs",
  "upsidedown",
  "elven",
  "onering",
  "island",
  "nostromo",
] as const;
export const NOTIFICATION_ANIMATIONS = [
  "slide",
  "fade",
  "pop",
  "zoom",
  "bounce",
  "flip",
  "swing",
  "glitch",
  "drop",
  "spiral",
  "slam",
  // 027: rise from below, wipe in, come into focus, jelly squash, arrive with a shake
  "rise",
  "wipe",
  "focus",
  "jelly",
  "shake",
  // 027: film transitions and the four elements
  "filmwipe",
  "iris",
  "air",
  "water",
  "earth",
  "fire",
  // 027: sucked into a black hole, melting, a comic « KAPOW! », a dimensional portal (they leave the same way)
  "blackhole",
  "melt",
  "kapow",
  "portal",
  "flipup",
  "balrog",
  "eye",
  "tracking",
  "morph",
  "uplink",
] as const;
/** 027: animated layers behind the portal (ambient) and celebrations — ``theme`` follows the theme. */
export const AMBIENTS = [
  "none",
  "snow",
  "embers",
  "code-rain",
  "fireflies",
  "starfield",
  "warp",
  "petals",
  "bats",
  "bubbles",
  "rain",
  "sparkles",
  "disco",
  "fog",
  "sand",
  "leaves",
  "hearts",
  "glitch",
  "lights",
  "spores",
  "aurora",
  // 027: VHS tracking, wind, tide, sky lanterns, 8-bit sky
  "vhs",
  "wind",
  "tide",
  "lanterns",
  "pixelsky",
  "upsidedown",
  "veins",
  "meadow",
  "ash",
  "bokeh",
  "nostromo",
  // #68: premium ambiences, drawn on a canvas (WebGL shaders, particles)
  "inferno",
  "thunderstorm",
  "sandstorm",
  "polar",
  "cosmos",
  "abyss",
  "blizzard",
  "fireworks",
  "downpour",
  "matrix",
  "mesh",
  "meshwave",
  "volcano",
  "blackhole",
  "reef",
  "firestorm",
  "whiteout",
  "liquidmetal",
  "plasma",
  "forest",
  "neoncity",
  "weather",
  "haunted",
  "darkness",
  "lostsignal",
  "garland",
  "christmasnight",
  "hearth",
  "goldenhour",
  "windowrain",
  "summerfield",
  "soapbubbles",
  "skylanterns",
  "autumnlane",
  "pixelcamp",
  "pixelbeach",
  "pixelballoons",
] as const;
/**
 * 027: the look of the level (XP) badge, worn on the profile (everyone sees it): ``classic`` is free and
 * changes with the level, the others are sold in the shop or given by achievements.
 */
export const LEVEL_BADGES = [
  "classic",
  "pixel",
  "neon",
  "crest",
  "gem",
  "hologram",
  "vhs",
  "saber",
  "elements",
  "blackhole",
  "melt",
  "kapow",
  "portal",
  "crown",
  "inferno",
  "upsidedown",
  "veins",
  "lights",
  "onering",
  "eye",
  "mithril",
  "balrog",
  "frost",
  "nebula",
  "circuit",
  "cassette",
  "squircle",
  "tracker",
] as const;
export type LevelBadge = (typeof LEVEL_BADGES)[number];
/** 027: how a level-up is shown — ``classic`` is free, each universe has its own (the theme's default). */
export const LEVEL_UPS = [
  "classic",
  "arcade",
  "cosmic",
  "comic",
  "elements",
  "cinema",
  "crawl",
  "spell",
  "decode",
  "sandstorm",
  "bloodmoon",
  "pumpkin",
  "gift",
  "manga",
  "boing",
  "hearth",
  "hud",
  "minimal",
  "abduction",
  "hero",
  "synthwave",
  "disco",
  "glitch",
  "noir",
  "spotlight",
  "upsidedown",
  "onering",
  "vhs",
  "nova",
  "nostromo",
] as const;
export type LevelUpLook = (typeof LEVEL_UPS)[number];
export const CELEBRATION_KEYS = [
  "none",
  "sparkle",
  "confetti",
  "glow",
  "snow",
  "bats",
  "pixels",
  "hearts",
  "stars",
  "coins",
  "lightning",
  "petals",
  "bubbles",
  "assemble",
  "burn",
  "shatter",
  "freeze",
  "glitch",
  "portal",
  "flicker",
  "fireworks",
  "rewind",
  "bloom",
  "tracker",
] as const;
export type Ambient = (typeof AMBIENTS)[number];
export type CelebrationKey = (typeof CELEBRATION_KEYS)[number];
export type NotificationStyle = (typeof NOTIFICATION_STYLES)[number];
export type NotificationAnimation = (typeof NOTIFICATION_ANIMATIONS)[number];

export interface UiPreferences {
  theme: string | null;
  density: Density;
  textScale: number;
  contrast: "default" | "high";
  reducedMotion: ReducedMotion;
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
  pick("notificationPosition", ["top-end", "top-start", "bottom-end", "bottom-start"]);
  pick("notificationStyle", ["theme", ...NOTIFICATION_STYLES]);
  pick("notificationAnimation", ["theme", ...NOTIFICATION_ANIMATIONS]);
  pick("ambient", ["theme", ...AMBIENTS]);
  pick("celebration", ["theme", ...CELEBRATION_KEYS]);
  pick("palette", PALETTE_KEYS);
  pick("levelUp", ["theme", ...LEVEL_UPS]);
  pick("campaignThemes", ["allow", "ignore"]);
  pick("colorMode", ["dark", "light", "system"]);
  if (typeof raw.soundEnabled === "boolean") out.soundEnabled = raw.soundEnabled;
  if (typeof raw.textScale === "number" && Number.isFinite(raw.textScale)) out.textScale = raw.textScale;
  if (typeof raw.notificationDurationSeconds === "number") {
    out.notificationDurationSeconds = Math.min(60, Math.max(2, Math.round(raw.notificationDurationSeconds)));
  }
  return out;
}
