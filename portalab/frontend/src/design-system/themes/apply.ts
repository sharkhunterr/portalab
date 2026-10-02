import { themeKeyFor } from "../a11y/contrast";
import { reducedMotionActive, systemPrefersReducedMotion } from "../a11y/motion";
import type { UiPolicy, UiPreferences } from "../a11y/preferences";
import { effectiveTextScale } from "../a11y/textScale";
import { BUILTIN_THEMES, builtinTheme, DEFAULT_THEME_KEY } from "./builtin";
import { floorReport } from "./floor";
import { FUNCTIONAL_STATES, type ThemeDefinition } from "./schema";

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
  requestedTheme: string | null;
  fallback: boolean;
  reducedMotion: boolean;
  textScale: number;
  overlay: string | null;
}

const COLOR_VARS: Record<keyof ThemeDefinition["colors"], string> = {
  surface: "--color-surface",
  surfaceRaised: "--color-surface-raised",
  text: "--color-text",
  textMuted: "--color-text-muted",
  border: "--color-border",
  accent: "--color-accent",
  accentContrast: "--color-accent-contrast",
  focus: "--color-focus",
};

export function resolve(
  preferences: UiPreferences,
  policy: UiPolicy,
  available: readonly ThemeDefinition[],
  options: { overlay?: CampaignOverlay | null; systemReducedMotion?: boolean } = {},
): Effective {
  const pool = available.length ? available : BUILTIN_THEMES;
  const usable = (key: string | null | undefined) =>
    key
      ? pool.find((t) => t.key === key && (policy.allowedThemes.includes(key) || key === "high-contrast"))
      : undefined;
  const requested = preferences.theme;
  const chosen = usable(themeKeyFor(preferences, requested ?? policy.defaultTheme));
  const theme =
    chosen ??
    usable(policy.defaultTheme) ??
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
  return {
    theme: effective,
    requestedTheme: requested,
    fallback: requested !== null && chosen?.key !== themeKeyFor(preferences, requested),
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
    root.style.setProperty(variable, theme.colors[role as keyof ThemeDefinition["colors"]]);
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
  const motion = effective.reducedMotion
    ? { fastMs: 0, normalMs: 0 }
    : (theme.motion ?? { fastMs: 120, normalMs: 220 });
  root.style.setProperty("--motion-duration-fast", `${motion.fastMs}ms`);
  root.style.setProperty("--motion-duration-normal", `${motion.normalMs}ms`);
  root.style.setProperty("--text-scale", String(effective.textScale));
  root.dataset.theme = theme.key;
  root.dataset.colorScheme = theme.colorScheme;
  root.dataset.contrast = preferences.contrast;
  root.dataset.density = preferences.density;
  root.dataset.reducedMotion = String(effective.reducedMotion);
  root.style.colorScheme = theme.colorScheme;
}
