import { readMirror } from "../a11y/PreferencesProvider";
import { DEFAULT_POLICY, DEFAULT_PREFERENCES } from "../a11y/preferences";
import { applyToDocument, resolve } from "./apply";
import { BUILTIN_THEMES } from "./builtin";
import { mirroredTheme } from "./mirror";

/** Apply the mirrored preferences before React renders, so the first paint already uses them. */
export function applyFirstPaint(): void {
  try {
    const mirror = readMirror();
    const preferences = mirror?.preferences ?? DEFAULT_PREFERENCES;
    const policy = { ...DEFAULT_POLICY, ...(mirror?.policy ?? {}) };
    // 028: the socle's interfaces, and the member's own as last applied here (the others are their packs')
    const mirrored = mirroredTheme();
    const themes = mirrored
      ? [...BUILTIN_THEMES.filter((t) => t.key !== mirrored.key), mirrored]
      : BUILTIN_THEMES;
    applyToDocument(resolve(preferences, policy, themes), preferences);
  } catch {
    // keep the CSS defaults
  }
}
