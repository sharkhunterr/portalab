import { parseTheme, type ThemeDefinition } from "./schema";

/**
 * 028: the interface last applied, mirrored in this browser — the interfaces are their packs' (only the
 * socle's ship in the code), so the first paint draws the member's own before the server answers. A per
 * browser convenience: absent, broken or refused storage simply leaves the socle's default.
 */
const KEY = "portalab.theme";

export function mirrorTheme(theme: ThemeDefinition): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(theme));
  } catch {
    // storage refused: the first paint keeps the socle's default
  }
}

export function mirroredTheme(): ThemeDefinition | undefined {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? parseTheme(JSON.parse(raw)).theme : undefined;
  } catch {
    return undefined;
  }
}
