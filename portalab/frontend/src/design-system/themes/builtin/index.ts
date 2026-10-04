import type { ThemeDefinition } from "../schema";
import dark from "./dark.json";
import highContrast from "./high-contrast.json";
import light from "./light.json";
import portalabDark from "./portalab-dark.json";
import portalabLight from "./portalab-light.json";

/** Built-in themes (also seeded by the backend ``ui`` migrations; a test keeps both copies identical). */
export const BUILTIN_THEMES: readonly ThemeDefinition[] = [
  portalabDark,
  portalabLight,
  light,
  dark,
  highContrast,
] as ThemeDefinition[];
/** The default theme family (027 R8) and its default member. */
export const DEFAULT_FAMILY = "portalab";
export const DEFAULT_THEME_KEY = "portalab-dark";
export const HIGH_CONTRAST_KEY = "high-contrast";

export function builtinTheme(key: string): ThemeDefinition | undefined {
  return BUILTIN_THEMES.find((theme) => theme.key === key);
}
