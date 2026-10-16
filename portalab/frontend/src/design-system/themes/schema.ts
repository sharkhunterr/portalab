import { z } from "zod";
import { isColor } from "./contrast";

/**
 * ``ThemeDefinition`` (spec 022 R2/R3): a **closed**, declarative document. Themes are inert data: colors,
 * typography, radii, motion, icons, backgrounds (bundled assets or raster data URIs only), sounds (bundled
 * assets) and notification defaults — no scripts, no CSS, no external URLs, no unknown keys. Every one of
 * the ten functional states must be mapped; a theme changes how a state looks, never which states exist.
 */

export const FUNCTIONAL_STATES = [
  "loading",
  "available",
  "partial",
  "stale",
  "error",
  "unavailable",
  "maintenance",
  "unauthorized",
  "no-data",
  "syncing",
] as const;
export type FunctionalStateName = (typeof FUNCTIONAL_STATES)[number];
export const CRITICAL_STATES: readonly FunctionalStateName[] = [
  "error",
  "unauthorized",
  "maintenance",
  "unavailable",
];
export const ICON_IDS = [
  "spinner",
  "check",
  "half",
  "clock",
  "warning",
  "blocked",
  "wrench",
  "lock",
  "lines",
  "sync",
] as const;

export const THEME_SCHEMA_VERSION = 2;
/** What a native color picker shows for a non-hex color (rgb()/rgba() are edited as text). */
export const COLOR_PICKER_FALLBACK = "#000000";

/**
 * Layout, motion and sound vocabulary (spec 027 R7/R24): a theme *chooses* among arrangements the portal
 * implements — including ones that change the arrangement principle (header as a footer bar, an orbit
 * bubble instead of a menu) — and never ships structure or code of its own.
 */
export const NAV_DESKTOP = [
  "sidebar",
  "topbar",
  "rail",
  "orbit",
  "dock",
  "tabs",
  "launcher",
  "terminal",
  "reel",
  "lights",
  "vcr",
  "sheet",
  "console",
  "taskbar",
  "feed",
  "player",
  "masthead",
  "dpad",
  "planisphere", // issue 130: the observatory
  "system", // issue 130: the space station
  "deck", // issue 130: the starship
] as const;
export const NAV_TABLET = [
  "rail",
  "topbar",
  "drawer",
  "orbit",
  "dock",
  "tabs",
  "launcher",
  "terminal",
  "reel",
  "lights",
  "vcr",
  "sheet",
  "console",
  "taskbar",
  "feed",
  "player",
  "masthead",
  "dpad",
  "planisphere", // issue 130: the observatory
  "system", // issue 130: the space station
  "deck", // issue 130: the starship
] as const;
export const NAV_PHONE = [
  "bottom-bar",
  "drawer",
  "orbit",
  "dock",
  "tabs",
  "launcher",
  "terminal",
  "reel",
  "lights",
  "vcr",
  "sheet",
  "console",
  "taskbar",
  "feed",
  "player",
  "masthead",
  "dpad",
  "planisphere", // issue 130: the observatory
  "system", // issue 130: the space station
  "deck", // issue 130: the starship
] as const;
export const HEADER_STYLES = ["full", "compact", "centered"] as const;
export const HEADER_POSITIONS = ["top", "bottom"] as const;
export const CARD_STYLES = [
  "elevated",
  "flat",
  "outlined",
  "glass",
  "comic",
  "neon",
  "paper",
  "pixel",
  "terminal",
  "ornate",
  "hologram",
  "console",
  "window",
] as const;
export const CONTENT_WIDTHS = ["narrow", "wide", "full"] as const;
export const CORNER_STYLES = ["square", "soft", "round"] as const;
export const WIDGET_FRAMES = ["card", "plain", "glass"] as const;
export const MOTION_PROFILES = ["none", "subtle", "lively", "playful"] as const;
/** issue 1: a navigation a theme names — one Portalab draws on this screen, or an imported pack's (the server
 * checked it exists) */
function openLook<T extends readonly [string, ...string[]]>(builtin: T) {
  return z.union([z.enum(builtin), z.string().regex(LOOK_KEY)]) as unknown as z.ZodEnum<{
    [K in T[number]]: K;
  }>;
}
/** 028: a look a theme names — a visual pack's (Portalab's own included): none is listed here, the server
 * checked it exists */
const LOOK_KEY = /^[a-z0-9][a-z0-9_.-]{0,63}$/;
const look = () => z.string().regex(LOOK_KEY);

/** 027: what a theme draws behind the portal — a static pattern and an animated ambient layer. */
export const BACKDROP_PATTERNS = [
  "none",
  "stars",
  "grid",
  "scanlines",
  "halftone",
  "dots",
  "parchment",
  "dunes",
  "circuit",
  "hexagons",
  "stripes",
  "sunburst",
  "checker",
  "noise",
  "waves",
  "plaid",
  "webs",
  "speedlines",
  "rays",
  "marble",
] as const;
export const HEADING_CASES = ["none", "uppercase", "smallcaps"] as const;
export const HEADING_EFFECTS = ["none", "glow", "gradient", "shadow", "outline", "neon", "emboss"] as const;
export const SOUND_EVENTS = ["notification", "alert", "success", "reward", "levelUp", "ui"] as const;
export const RARITIES = ["common", "rare", "epic", "legendary"] as const;

const color = z.string().max(64).refine(isColor, { message: "expected a #hex or rgb()/rgba() color" });
const asset = z.string().regex(/^asset:[a-z0-9][a-z0-9._/-]{0,127}$/, "expected a bundled asset reference");
const rasterDataUri = z
  .string()
  .max(200_000)
  .regex(/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/, "only raster data URIs are allowed");
const labelKey = z.string().regex(/^[a-z][a-zA-Z0-9_.-]{0,127}$/);
const iconName = z.string().regex(/^[a-z][a-z0-9-]{0,31}$/);
/** 027: a theme's own words for the portal (navigation, page titles, currency) — plain text, no markup. */
const vocabulary = z
  .record(
    z.string().regex(/^[a-z][a-z0-9_-]*:[a-zA-Z0-9_.-]{1,120}$/),
    z
      .string()
      .min(1)
      .max(60)
      .regex(/^[^{}<>]+$/, "plain text only"),
  )
  .refine((value) => Object.keys(value).length <= 120, { message: "at most 120 terms" });
const fontFamily = z
  .string()
  .max(200)
  .regex(/^[A-Za-z0-9 ,"'-]+$/, "font family names only");

const stateStyle = z.strictObject({
  fg: color,
  bg: color,
  icon: z.enum(ICON_IDS).optional(),
  label: labelKey.optional(),
  opacity: z.number().min(0).max(1).optional(),
  display: z.enum(["inline", "block", "none"]).optional(),
});

const layoutSchema = z.strictObject({
  nav: z
    .strictObject({
      desktop: openLook(NAV_DESKTOP).optional(),
      tablet: openLook(NAV_TABLET).optional(),
      phone: openLook(NAV_PHONE).optional(),
    })
    .optional(),
  header: z.enum(HEADER_STYLES).optional(),
  headerPosition: z.enum(HEADER_POSITIONS).optional(),
  cards: z.enum(CARD_STYLES).optional(),
  content: z.enum(CONTENT_WIDTHS).optional(),
  corners: z.enum(CORNER_STYLES).optional(),
  widgetFrame: z.enum(WIDGET_FRAMES).optional(),
});

export const themeDefinitionSchema = z.strictObject({
  schemaVersion: z.union([z.literal(1), z.literal(THEME_SCHEMA_VERSION)]),
  key: z.string().regex(/^[a-z][a-z0-9-]{1,47}$/),
  name: z.string().min(1).max(80),
  family: z
    .string()
    .regex(/^[a-z][a-z0-9-]{1,47}$/)
    .optional(),
  colorScheme: z.enum(["light", "dark"]),
  colors: z.strictObject({
    surface: color,
    surfaceRaised: color,
    text: color,
    textMuted: color,
    border: color,
    accent: color,
    accentContrast: color,
    focus: color,
    accentAlt: color.optional(),
    rarity: z
      .strictObject(
        Object.fromEntries(RARITIES.map((rarity) => [rarity, color])) as Record<
          (typeof RARITIES)[number],
          typeof color
        >,
      )
      .optional(),
  }),
  states: z.strictObject(
    Object.fromEntries(FUNCTIONAL_STATES.map((state) => [state, stateStyle])) as Record<
      FunctionalStateName,
      typeof stateStyle
    >,
  ),
  typography: z
    .strictObject({
      fontFamily: fontFamily.optional(),
      /** 027: titles and headings — a display font, its case and effect. */
      headingFamily: fontFamily.optional(),
      headingCase: z.enum(HEADING_CASES).optional(),
      headingEffect: z.enum(HEADING_EFFECTS).optional(),
      scale: z
        .strictObject({
          sm: z.number().min(0.75).max(1.25),
          md: z.number().min(0.875).max(1.5),
          lg: z.number().max(2.5),
          xl: z.number().max(3.5),
        })
        .optional(),
    })
    .optional(),
  radii: z.strictObject({ sm: z.number().min(0).max(2), md: z.number().min(0).max(3) }).optional(),
  motion: z
    .strictObject({
      fastMs: z.number().int().min(0).max(1000).optional(),
      normalMs: z.number().int().min(0).max(2000).optional(),
      profile: z.enum(MOTION_PROFILES).optional(),
      celebration: look().optional(),
      levelUp: look().optional(), // 027: how this theme celebrates a new level
    })
    .optional(),
  layout: layoutSchema.optional(),
  icons: z
    .strictObject({
      set: z.enum(["default", "outline"]),
      /** 027: the theme's own icons (``home`` → ``castle``), among the portal's icons. */
      overrides: z
        .record(iconName, iconName)
        .refine((value) => Object.keys(value).length <= 60, { message: "at most 60 icons" })
        .optional(),
    })
    .optional(),
  background: z
    .strictObject({
      image: z.union([asset, rasterDataUri]).optional(),
      fallback: color,
      pattern: z.enum(BACKDROP_PATTERNS).optional(),
      ambient: look().optional(),
    })
    .optional(),
  vocabulary: z
    .record(z.string().regex(/^[a-z]{2,3}$/), vocabulary)
    .refine((value) => Object.keys(value).length <= 12, { message: "at most 12 languages" })
    .optional(),
  sounds: z.partialRecord(z.enum(SOUND_EVENTS), asset).optional(),
  notification: z
    .strictObject({
      position: z.enum(["top-end", "top-start", "bottom-end", "bottom-start"]).optional(),
      durationSeconds: z.number().int().min(2).max(60).optional(),
      style: look().optional(),
      animation: look().optional(),
    })
    .optional(),
});

export type ThemeDefinition = z.infer<typeof themeDefinitionSchema>;
export type ThemeLayout = z.infer<typeof layoutSchema>;

/** Every layout/motion choice resolved — v1 documents and partial v2 documents get the defaults. */
export interface ResolvedPresentation {
  nav: {
    desktop: (typeof NAV_DESKTOP)[number];
    tablet: (typeof NAV_TABLET)[number];
    phone: (typeof NAV_PHONE)[number];
  };
  header: (typeof HEADER_STYLES)[number];
  headerPosition: (typeof HEADER_POSITIONS)[number];
  cards: (typeof CARD_STYLES)[number];
  content: (typeof CONTENT_WIDTHS)[number];
  corners: (typeof CORNER_STYLES)[number];
  widgetFrame: (typeof WIDGET_FRAMES)[number];
  motion: (typeof MOTION_PROFILES)[number];
  celebration: string;
  fastMs: number;
  normalMs: number;
}

export function presentationOf(theme: ThemeDefinition): ResolvedPresentation {
  const layout = theme.layout ?? {};
  const motion = theme.motion ?? {};
  return {
    nav: {
      desktop: layout.nav?.desktop ?? "sidebar",
      tablet: layout.nav?.tablet ?? "rail",
      phone: layout.nav?.phone ?? "drawer",
    },
    header: layout.header ?? "full",
    headerPosition: layout.headerPosition ?? "top",
    cards: layout.cards ?? "elevated",
    content: layout.content ?? "wide",
    corners: layout.corners ?? "soft",
    widgetFrame: layout.widgetFrame ?? "card",
    motion: motion.profile ?? "subtle",
    celebration: motion.celebration ?? "sparkle",
    fastMs: motion.fastMs ?? 120,
    normalMs: motion.normalMs ?? 220,
  };
}

/** Upgrade a stored document to the current schema version (new blocks are optional: nothing to invent). */
export function upgradeTheme(theme: ThemeDefinition): ThemeDefinition {
  return theme.schemaVersion === THEME_SCHEMA_VERSION
    ? theme
    : { ...theme, schemaVersion: THEME_SCHEMA_VERSION };
}

export function parseTheme(value: unknown): { theme?: ThemeDefinition; errors: string[] } {
  const result = themeDefinitionSchema.safeParse(value);
  if (result.success) {
    return { theme: upgradeTheme(result.data), errors: [] };
  }
  return {
    errors: result.error.issues.map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`),
  };
}

/** JSON Schema of the theme document, shared with the backend registry (``modules/ui``). */
export function themeJsonSchema(): unknown {
  return z.toJSONSchema(themeDefinitionSchema);
}
