import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { usePreferences } from "../a11y/PreferencesProvider";
import { sound } from "../sound/SoundService";
import { externalTheme, useExternalRevision } from "../visuals/registry";
import {
  applyToDocument,
  type CampaignOverlay,
  type Effective,
  type LockedLooks,
  type ResolvedLooks,
  resolve,
  resolveLooks,
} from "./apply";
import { BUILTIN_THEMES, builtinTheme } from "./builtin";
import { mirrorTheme } from "./mirror";
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
  /** issue 1: changes when an imported pack is installed or removed */
  externalRevision?: number;
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
  /** 027: the theme looks the member does not own (they fall back to the free defaults); ``null`` while
   * not known, absent when nothing is sold (a gallery, no Marketplace). */
  lockedLooks?: LockedLooks | null | undefined;
}

export function ThemeProvider({ children, themes, overlay = null, root, lockedLooks }: ThemeProviderProps) {
  const { preferences, policy, preview } = usePreferences();
  // issue 1: an imported pack installed or removed — its looks and palettes redrawn everywhere
  const externalRevision = useExternalRevision();
  const available = useMemo(() => {
    const valid = validThemes(themes ?? []);
    return valid.length ? valid : [...BUILTIN_THEMES];
  }, [themes]);
  const systemDark = useSystemDark(preferences.colorMode === "system");
  // biome-ignore lint/correctness/useExhaustiveDependencies: an imported interface is tried once loaded
  const trial = useMemo(
    () =>
      preview?.theme
        ? (available.find((theme) => theme.key === preview.theme) ??
          builtinTheme(preview.theme) ??
          externalTheme(preview.theme) ?? // issue 1: an imported interface tried before it is published
          null)
        : null,
    [preview?.theme, available, externalRevision],
  );
  const effective = useMemo(
    () => resolve(preferences, policy, available, { overlay, systemDark, trial }),
    [preferences, policy, available, overlay, systemDark, trial],
  );
  // biome-ignore lint/correctness/useExhaustiveDependencies: an imported palette applies once it is loaded
  useEffect(() => {
    sound.sounds = { ...(effective.theme.sounds ?? {}) }; // the theme's sound set (027 R18)
    try {
      applyToDocument(effective, preferences, root, lockedLooks);
      if (!root) mirrorTheme(effective.theme); // 028: the next first paint draws it before the server answers
    } catch {
      const fallback = builtinTheme(policy.defaultTheme) ?? (BUILTIN_THEMES[0] as ThemeDefinition);
      applyToDocument({ ...effective, theme: fallback }, preferences, root, lockedLooks);
    }
  }, [effective, preferences, policy.defaultTheme, root, lockedLooks, externalRevision]);
  const looks = useMemo(
    () => resolveLooks(effective, preferences, lockedLooks),
    [effective, preferences, lockedLooks],
  );
  const value = useMemo<ThemeContextValue>(
    () => ({
      effective,
      looks,
      themes: available,
      stateStyle: (state: string) => effective.theme.states[state as keyof ThemeDefinition["states"]],
      externalRevision,
    }),
    [effective, looks, available, externalRevision],
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
      levelUp: "classic",
    },
    themes: BUILTIN_THEMES,
    stateStyle: (state: string) => theme.states[state as keyof ThemeDefinition["states"]],
  };
}
