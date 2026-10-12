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
  // #81: the seasons
  "pumpkinspice",
  "evergreen",
  "cherry",
  "pastel",
  "tropical",
  // #89: the universes
  "scarletgold",
  "rum",
  "gunmetal",
  // #89: the desktop, the fruit company, the social network
  "luna",
  "graphite",
  "chatgradient",
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
  // #78: drawn by the GPU
  "blaze",
  "voltage",
  "aqua",
  "magma",
  "glacier",
  "galaxy",
  "aurum",
  "toxic",
  "holo",
  "runes",
  "matrix",
  "sakura",
  "shadow",
  "candy",
  "aurora",
  "plasma",
  "chrono",
  // #81: the seasons
  "tombstone",
  "giftwrap",
  "loveletter",
  "bloom",
  "postcard",
  // #89: the universes
  "scroll",
  "bottle",
  "chamfer",
  // #89: the desktop, the fruit company, the social network
  "balloon",
  "trafficlights",
  "chathead",
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
  // #78: drawn by the GPU
  "ignite",
  "surge",
  "splash",
  "frostbite",
  "stardust",
  "hex",
  "decrypt",
  "petalfall",
  "eclipse",
  "warp",
  // #89: the universes
  "swoop",
  "anchor",
  "transform",
  // #89: the desktop, the fruit company, the social network
  "trayrise",
  "genie",
  "chatpop",
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
  "amberglow",
  "candlelight",
  "steam",
  "fairybokeh",
  "warmsilk",
  "honey",
  "knit",
  "paintmix",
  "acrylicpour",
  "watercolor",
  "marbling",
  "poppaint",
  "poppour",
  "popwatercolor",
  "popmarbling",
  "lavalamp",
  "impasto",
  "paintribbon",
  // #81: the seasons
  "cobwebs",
  "ornaments",
  "loveletters",
  "butterflies",
  "seagulls",
  // #89: the universes
  "floatingcandles",
  "cannonsmoke",
  "gears",
  // #89: the desktop, the fruit company, the social network
  "skyclouds",
  "silkwaves",
  "reactions",
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
  // #73: drawn by the GPU
  "blaze",
  "voltage",
  "aqua",
  "magma",
  // #77: drawn by the GPU
  "glacier",
  "galaxy",
  "aurum",
  "toxic",
  "holo",
  "runes",
  "matrix",
  "sakura",
  "shadow",
  "candy",
  "aurora",
  "plasma",
  "chrono",
  // #81: the seasons
  "jackolantern",
  "bauble",
  "heart",
  "easteregg",
  "sunset",
  "spectre",
  "tinsel",
  "verdant",
  // #89: the universes
  "snitch",
  "doubloon",
  "chevron",
  // #89: the desktop, the fruit company, the social network
  "startbutton",
  "aquagel",
  "speechbubble",
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
  // #78: full-stage, drawn by the GPU
  "phoenix",
  "thunderstrike",
  "tidalwave",
  "supernova",
  "goldrush",
  "arcanum",
  "sakurastorm",
  "aurorasky",
  "timeportal",
  // #89: the universes
  "owlpost",
  "plunder",
  "rollout",
  // #89: the desktop, the fruit company, the social network
  "setupwizard",
  "unboxing",
  "viral",
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
  // #78: drawn by the GPU
  "nova",
  "goldshower",
  "petalstorm",
  "rebirth",
  "stormstrike",
  "skyveil",
  "arcana",
  "timerift",
  // #81: the seasons
  "candy",
  "gifts",
  "cupid",
  "eggs",
  "splash",
  // #89: the universes
  "wandsparks",
  "cannonball",
  "bolts",
  // #89: the desktop, the fruit company, the social network
  "cardcascade",
  "balloons",
  "likes",
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
