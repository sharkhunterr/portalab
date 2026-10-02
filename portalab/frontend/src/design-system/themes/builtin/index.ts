import type { ThemeDefinition } from "../schema";
import dark from "./dark.json";
import highContrast from "./high-contrast.json";
import light from "./light.json";

/** Built-in themes (also seeded by the backend ``ui`` migration; a test keeps both copies identical). */
export const BUILTIN_THEMES: readonly ThemeDefinition[] = [light, dark, highContrast] as ThemeDefinition[];
export const DEFAULT_THEME_KEY = "light";
export const HIGH_CONTRAST_KEY = "high-contrast";

export function builtinTheme(key: string): ThemeDefinition | undefined {
  return BUILTIN_THEMES.find((theme) => theme.key === key);
}
