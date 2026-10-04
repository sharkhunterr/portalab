import { themeKeyFor } from "../a11y/contrast";
import { reducedMotionActive, systemPrefersReducedMotion } from "../a11y/motion";
import type { UiPolicy, UiPreferences } from "../a11y/preferences";
import { effectiveTextScale } from "../a11y/textScale";
import { BUILTIN_THEMES, builtinTheme, DEFAULT_THEME_KEY } from "./builtin";
import { floorReport } from "./floor";
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
  options: { overlay?: CampaignOverlay | null; systemReducedMotion?: boolean; systemDark?: boolean } = {},
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

export function applyToDocument(
  effective: Effective,
  preferences: UiPreferences,
  root: HTMLElement = document.documentElement,
): void {
  const { theme } = effective;
  for (const [role, variable] of Object.entries(COLOR_VARS)) {
    root.style.setProperty(variable, theme.colors[role as BaseColor]);
  }
  root.style.setProperty("--color-accent-alt", theme.colors.accentAlt ?? theme.colors.accent);
  for (const rarity of RARITIES) {
    root.style.setProperty(`--rarity-${rarity}`, theme.colors.rarity?.[rarity] ?? theme.colors.accent);
  }
  for (const state of FUNCTIONAL_STATES) {
    root.style.setProperty(`--state-${state}-fg`, theme.states[state].fg);
    root.style.setProperty(`--state-${state}-bg`, theme.states[state].bg);
  }
  if (theme.typography?.fontFamily) root.style.setProperty("--font-sans", theme.typography.fontFamily);
  if (theme.radii) {
    root.style.setProperty("--radius-sm", `${theme.radii.sm}rem`);
    root.style.setProperty("--radius-md", `${theme.radii.md}rem`);
  }
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
  root.dataset.celebration = effective.reducedMotion ? "none" : presentation.celebration;
  root.style.setProperty("--text-scale", String(effective.textScale));
  root.dataset.theme = theme.key;
  root.dataset.colorScheme = theme.colorScheme;
  root.dataset.contrast = preferences.contrast;
  root.dataset.density = preferences.density;
  root.dataset.reducedMotion = String(effective.reducedMotion);
  root.style.colorScheme = theme.colorScheme;
}
