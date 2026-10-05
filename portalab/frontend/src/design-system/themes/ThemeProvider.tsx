import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { usePreferences } from "../a11y/PreferencesProvider";
import { sound } from "../sound/SoundService";
import {
  applyToDocument,
  type CampaignOverlay,
  type Effective,
  type ResolvedLooks,
  resolve,
  resolveLooks,
} from "./apply";
import { BUILTIN_THEMES, builtinTheme } from "./builtin";
import { parseTheme, type ThemeDefinition } from "./schema";

/**
 * ``ThemeProvider`` (spec 022 T013): applies the effective theme then the user's accessibility overrides
 * to ``<html>``; an invalid or unavailable theme falls back to the default (the preference is retained).
 * Applying a theme never re-renders data differently: it only changes CSS custom properties.
 */

interface ThemeContextValue {
  effective: Effective;
  /** 027: notification look, ambient layer and celebration actually used (preference or theme). */
  looks: ResolvedLooks;
  themes: readonly ThemeDefinition[];
  stateStyle: (state: string) => ThemeDefinition["states"][keyof ThemeDefinition["states"]] | undefined;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function validThemes(candidates: readonly unknown[]): ThemeDefinition[] {
  const valid: ThemeDefinition[] = [];
  for (const candidate of candidates) {
    const { theme } = parseTheme(candidate);
    if (theme) valid.push(theme);
  }
  return valid;
}

export interface ThemeProviderProps {
  children: ReactNode;
  themes?: readonly unknown[];
  overlay?: CampaignOverlay | null;
  root?: HTMLElement;
}

export function ThemeProvider({ children, themes, overlay = null, root }: ThemeProviderProps) {
  const { preferences, policy, preview } = usePreferences();
  const available = useMemo(() => {
    const valid = validThemes(themes ?? []);
    return valid.length ? valid : [...BUILTIN_THEMES];
  }, [themes]);
  const systemDark = useSystemDark(preferences.colorMode === "system");
  const trial = useMemo(
    () =>
      preview?.theme
        ? (available.find((theme) => theme.key === preview.theme) ?? builtinTheme(preview.theme) ?? null)
        : null,
    [preview?.theme, available],
  );
  const effective = useMemo(
    () => resolve(preferences, policy, available, { overlay, systemDark, trial }),
    [preferences, policy, available, overlay, systemDark, trial],
  );
  useEffect(() => {
    sound.sounds = { ...(effective.theme.sounds ?? {}) }; // the theme's sound set (027 R18)
    try {
      applyToDocument(effective, preferences, root);
    } catch {
      const fallback = builtinTheme(policy.defaultTheme) ?? (BUILTIN_THEMES[0] as ThemeDefinition);
      applyToDocument({ ...effective, theme: fallback }, preferences, root);
    }
  }, [effective, preferences, policy.defaultTheme, root]);
  const looks = useMemo(() => resolveLooks(effective, preferences), [effective, preferences]);
  const value = useMemo<ThemeContextValue>(
    () => ({
      effective,
      looks,
      themes: available,
      stateStyle: (state: string) => effective.theme.states[state as keyof ThemeDefinition["states"]],
    }),
    [effective, looks, available],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/** Follows the device light/dark preference while the user's color mode is ``system`` (027 R8). */
function useSystemDark(active: boolean): boolean {
  const query = "(prefers-color-scheme: dark)";
  const read = () =>
    typeof window === "undefined" ||
    typeof window.matchMedia !== "function" ||
    window.matchMedia(query).matches;
  const [dark, setDark] = useState(read);
  useEffect(() => {
    if (!active || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const update = () => setDark(media.matches);
    update();
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, [active]);
  return dark;
}

/** Current theme; outside a provider the built-in default applies (components never crash). */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (context) return context;
  const theme = BUILTIN_THEMES[0] as ThemeDefinition;
  return {
    effective: {
      theme,
      scheme: theme.colorScheme,
      requestedTheme: null,
      fallback: false,
      reducedMotion: false,
      textScale: 1,
      overlay: null,
    },
    looks: {
      notificationStyle: "toast",
      notificationAnimation: "slide",
      ambient: "none",
      celebration: "sparkle",
    },
    themes: BUILTIN_THEMES,
    stateStyle: (state: string) => theme.states[state as keyof ThemeDefinition["states"]],
  };
}
