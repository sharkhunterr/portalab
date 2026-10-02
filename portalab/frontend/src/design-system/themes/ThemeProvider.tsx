import { createContext, type ReactNode, useContext, useEffect, useMemo } from "react";
import { usePreferences } from "../a11y/PreferencesProvider";
import { applyToDocument, type CampaignOverlay, type Effective, resolve } from "./apply";
import { BUILTIN_THEMES, builtinTheme } from "./builtin";
import { parseTheme, type ThemeDefinition } from "./schema";

/**
 * ``ThemeProvider`` (spec 022 T013): applies the effective theme then the user's accessibility overrides
 * to ``<html>``; an invalid or unavailable theme falls back to the default (the preference is retained).
 * Applying a theme never re-renders data differently: it only changes CSS custom properties.
 */

interface ThemeContextValue {
  effective: Effective;
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
  const { preferences, policy } = usePreferences();
  const available = useMemo(() => {
    const valid = validThemes(themes ?? []);
    return valid.length ? valid : [...BUILTIN_THEMES];
  }, [themes]);
  const effective = useMemo(
    () => resolve(preferences, policy, available, { overlay }),
    [preferences, policy, available, overlay],
  );
  useEffect(() => {
    try {
      applyToDocument(effective, preferences, root);
    } catch {
      const fallback = builtinTheme(policy.defaultTheme) ?? (BUILTIN_THEMES[0] as ThemeDefinition);
      applyToDocument({ ...effective, theme: fallback }, preferences, root);
    }
  }, [effective, preferences, policy.defaultTheme, root]);
  const value = useMemo<ThemeContextValue>(
    () => ({
      effective,
      themes: available,
      stateStyle: (state: string) => effective.theme.states[state as keyof ThemeDefinition["states"]],
    }),
    [effective, available],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/** Current theme; outside a provider the built-in default applies (components never crash). */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (context) return context;
  const theme = BUILTIN_THEMES[0] as ThemeDefinition;
  return {
    effective: {
      theme,
      requestedTheme: null,
      fallback: false,
      reducedMotion: false,
      textScale: 1,
      overlay: null,
    },
    themes: BUILTIN_THEMES,
    stateStyle: (state: string) => theme.states[state as keyof ThemeDefinition["states"]],
  };
}
