import { themeKeyFor } from "../a11y/contrast";
import { reducedMotionActive, systemPrefersReducedMotion } from "../a11y/motion";
import type {
  Ambient,
  CelebrationKey,
  LevelUpLook,
  NotificationAnimation,
  NotificationStyle,
  UiPolicy,
  UiPreferences,
} from "../a11y/preferences";
import { effectiveTextScale } from "../a11y/textScale";
import { BUILTIN_THEMES, builtinTheme, DEFAULT_THEME_KEY } from "./builtin";
import { floorReport } from "./floor";
import { paletteFor } from "./palettes";
import { FUNCTIONAL_STATES, presentationOf, RARITIES, type ThemeDefinition } from "./schema";

/**
 * Resolve and apply the effective presentation: theme (allowed + available, else the policy default,
 * else the built-in default) → optional campaign overlay (only if allowed and passing the floor) → user
 * accessibility overrides (high contrast, reduced motion, text scale, density), which always win.
 * Everything lands as CSS custom properties / data attributes on ``<html>``; nothing changes data.
 */

export interface CampaignOverlay {
  key: string;
  colors?: Partial<ThemeDefinition["colors"]>;
}

export interface Effective {
  theme: ThemeDefinition;
  /** The light/dark scheme actually shown (027 R8). */
  scheme: "light" | "dark";
  requestedTheme: string | null;
  fallback: boolean;
  reducedMotion: boolean;
  textScale: number;
  overlay: string | null;
}

type BaseColor = Exclude<keyof ThemeDefinition["colors"], "accentAlt" | "rarity">;

const COLOR_VARS: Record<BaseColor, string> = {
  surface: "--color-surface",
  surfaceRaised: "--color-surface-raised",
  text: "--color-text",
  textMuted: "--color-text-muted",
  border: "--color-border",
  accent: "--color-accent",
  accentContrast: "--color-accent-contrast",
  focus: "--color-focus",
};

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : true;
}

/** The scheme a color mode asks for: an explicit mode, or the device preference for ``system``. */
export function schemeFor(
  mode: UiPreferences["colorMode"],
  systemDark = systemPrefersDark(),
): "light" | "dark" {
  if (mode === "system") return systemDark ? "dark" : "light";
  return mode;
}

export function resolve(
  preferences: UiPreferences,
  policy: UiPolicy,
  available: readonly ThemeDefinition[],
  options: {
    overlay?: CampaignOverlay | null;
    systemReducedMotion?: boolean;
    systemDark?: boolean;
    /** 027: a theme tried on in the shop — shown even if not owned yet. */
    trial?: ThemeDefinition | null;
  } = {},
): Effective {
  const pool = available.length ? available : BUILTIN_THEMES;
  const allowed = (theme: ThemeDefinition) =>
    policy.allowedThemes.includes(theme.key) || theme.key === "high-contrast";
  const scheme = schemeFor(preferences.colorMode, options.systemDark);
  // A key may name a theme or a theme family (027 R8): a family resolves to its member for the color mode.
  const usable = (key: string | null | undefined): ThemeDefinition | undefined => {
    if (!key) return undefined;
    const direct = pool.find((t) => t.key === key && allowed(t));
    if (direct) return direct;
    const members = pool.filter((t) => t.family === key && allowed(t));
    return members.find((t) => t.colorScheme === scheme) ?? members[0];
  };
  const requested = preferences.theme;
  const chosen = usable(themeKeyFor(preferences, requested ?? policy.defaultTheme));
  const theme =
    options.trial ??
    chosen ??
    usable(policy.defaultTheme) ??
    pool.find((t) => policy.allowedThemes.includes(t.key)) ?? // the first allowed theme (027)
    builtinTheme(policy.defaultTheme) ??
    (builtinTheme(DEFAULT_THEME_KEY) as ThemeDefinition);
  let effective = theme;
  let overlay: string | null = null;
  if (options.overlay && preferences.campaignThemes === "allow" && preferences.contrast !== "high") {
    const merged = { ...theme, colors: { ...theme.colors, ...(options.overlay.colors ?? {}) } };
    if (floorReport(merged).ok) {
      effective = merged;
      overlay = options.overlay.key;
    }
  }
  const wanted = requested === null ? null : themeKeyFor(preferences, requested);
  return {
    theme: effective,
    scheme: effective.colorScheme,
    requestedTheme: requested,
    fallback: wanted !== null && chosen?.key !== wanted && chosen?.family !== wanted,
    reducedMotion: reducedMotionActive(
      preferences.reducedMotion,
      policy,
      options.systemReducedMotion ?? systemPrefersReducedMotion(),
    ),
    textScale: effectiveTextScale(preferences.textScale, policy),
    overlay,
  };
}

/** 027: the member's choices resolved against the theme's defaults (``theme`` follows the theme). */
export interface ResolvedLooks {
  notificationStyle: NotificationStyle;
  notificationAnimation: NotificationAnimation;
  ambient: Ambient;
  celebration: CelebrationKey;
  /** 027: the level-up moment's look (the member's, or the theme's own). */
  levelUp: LevelUpLook;
}

/**
 * 027: the looks a member may not wear (sold in the shop, not owned, not free), per kind. A theme's own
 * look counts as one of them: the theme alone brings its colours, fonts, layout and words, while its
 * sold looks (ambience, notifications, celebration, level-up) come with the universe's pack — without
 * them, « follow the theme » falls back to the free default. ``null``: not known yet (all fall back).
 */
export interface LockedLooks {
  notificationStyle?: ReadonlySet<string>;
  notificationAnimation?: ReadonlySet<string>;
  ambient?: ReadonlySet<string>;
  celebration?: ReadonlySet<string>;
  levelUp?: ReadonlySet<string>;
}

/** The free defaults a theme's look falls back to when the member does not own it. */
export const FREE_LOOKS: ResolvedLooks = {
  notificationStyle: "toast",
  notificationAnimation: "slide",
  ambient: "none",
  celebration: "sparkle",
  levelUp: "classic",
};

export function resolveLooks(
  effective: Effective,
  preferences: UiPreferences,
  locked?: LockedLooks | null,
): ResolvedLooks {
  const theme = effective.theme;
  const presentation = presentationOf(theme);
  // the theme's own look, if the member may wear it
  const own = <K extends keyof ResolvedLooks>(kind: K, value: ResolvedLooks[K]): ResolvedLooks[K] => {
    if (locked === undefined || value === FREE_LOOKS[kind]) return value;
    if (locked === null || locked[kind]?.has(value)) return FREE_LOOKS[kind];
    return value;
  };
  const ambient =
    preferences.ambient === "theme"
      ? own("ambient", (theme.background?.ambient ?? "none") as Ambient)
      : preferences.ambient;
  return {
    notificationStyle:
      preferences.notificationStyle === "theme"
        ? own("notificationStyle", (theme.notification?.style ?? "toast") as NotificationStyle)
        : preferences.notificationStyle,
    notificationAnimation:
      preferences.notificationAnimation === "theme"
        ? own("notificationAnimation", (theme.notification?.animation ?? "slide") as NotificationAnimation)
        : preferences.notificationAnimation,
    ambient: effective.reducedMotion || preferences.contrast === "high" ? "none" : ambient,
    celebration: effective.reducedMotion
      ? "none"
      : preferences.celebration === "theme"
        ? own("celebration", presentation.celebration as CelebrationKey)
        : preferences.celebration,
    levelUp:
      preferences.levelUp === "theme"
        ? own("levelUp", (theme.motion?.levelUp ?? "classic") as LevelUpLook)
        : preferences.levelUp,
  };
}

function setOrRemove(root: HTMLElement, name: string, value: string | undefined): void {
  if (value) root.style.setProperty(name, value);
  else root.style.removeProperty(name);
}

export function applyToDocument(
  effective: Effective,
  preferences: UiPreferences,
  root: HTMLElement = document.documentElement,
  locked?: LockedLooks | null,
): void {
  const { theme } = effective;
  for (const [role, variable] of Object.entries(COLOR_VARS)) {
    root.style.setProperty(variable, theme.colors[role as BaseColor]);
  }
  root.style.setProperty("--color-accent-alt", theme.colors.accentAlt ?? theme.colors.accent);
  // 027: a colour palette over the theme (accents only), never in high contrast
  const palette =
    preferences.contrast === "high"
      ? null
      : paletteFor(preferences.palette, theme.colorScheme === "light" ? "light" : "dark");
  if (palette) {
    root.style.setProperty("--color-accent", palette.accent);
    root.style.setProperty("--color-accent-alt", palette.accentAlt);
    root.style.setProperty("--color-accent-contrast", palette.contrast);
  }
  for (const rarity of RARITIES) {
    root.style.setProperty(`--rarity-${rarity}`, theme.colors.rarity?.[rarity] ?? theme.colors.accent);
  }
  for (const state of FUNCTIONAL_STATES) {
    root.style.setProperty(`--state-${state}-fg`, theme.states[state].fg);
    root.style.setProperty(`--state-${state}-bg`, theme.states[state].bg);
  }
  // fonts: a theme's text and heading faces (027) — removed again when the next theme has none
  setOrRemove(root, "--font-sans", theme.typography?.fontFamily);
  setOrRemove(root, "--font-display", theme.typography?.headingFamily ?? theme.typography?.fontFamily);
  root.dataset.headingCase = theme.typography?.headingCase ?? "none";
  root.dataset.headingEffect =
    preferences.contrast === "high" ? "none" : (theme.typography?.headingEffect ?? "none");
  setOrRemove(root, "--radius-sm", theme.radii ? `${theme.radii.sm}rem` : undefined);
  setOrRemove(root, "--radius-md", theme.radii ? `${theme.radii.md}rem` : undefined);
  root.dataset.backdrop = preferences.contrast === "high" ? "none" : (theme.background?.pattern ?? "none");
  const presentation = presentationOf(theme);
  const motion = effective.reducedMotion ? { fastMs: 0, normalMs: 0 } : presentation;
  root.style.setProperty("--motion-duration-fast", `${motion.fastMs}ms`);
  root.style.setProperty("--motion-duration-normal", `${motion.normalMs}ms`);
  // Layout, motion and celebration choices (027 R7/R24) — CSS and the shell switch on these attributes.
  root.dataset.navDesktop = presentation.nav.desktop;
  root.dataset.navTablet = presentation.nav.tablet;
  root.dataset.navPhone = presentation.nav.phone;
  root.dataset.header = presentation.header;
  root.dataset.headerPosition = presentation.headerPosition;
  root.dataset.cards = presentation.cards;
  root.dataset.content = presentation.content;
  root.dataset.corners = presentation.corners;
  root.dataset.widgetFrame = presentation.widgetFrame;
  root.dataset.motion = effective.reducedMotion ? "none" : presentation.motion;
  const looks = resolveLooks(effective, preferences, locked);
  root.dataset.celebration = looks.celebration;
  root.dataset.ambient = looks.ambient;
  root.style.setProperty("--text-scale", String(effective.textScale));
  root.dataset.theme = theme.key;
  root.dataset.palette = palette ? preferences.palette : "theme";
  root.dataset.colorScheme = theme.colorScheme;
  root.dataset.contrast = preferences.contrast;
  root.dataset.density = preferences.density;
  root.dataset.reducedMotion = String(effective.reducedMotion);
  root.style.colorScheme = theme.colorScheme;
}
