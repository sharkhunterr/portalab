import { readMirror } from "../a11y/PreferencesProvider";
import { DEFAULT_POLICY, DEFAULT_PREFERENCES } from "../a11y/preferences";
import { applyToDocument, resolve } from "./apply";
import { BUILTIN_THEMES } from "./builtin";

/** Apply the mirrored preferences before React renders, so the first paint already uses them. */
export function applyFirstPaint(): void {
  try {
    const mirror = readMirror();
    const preferences = mirror?.preferences ?? DEFAULT_PREFERENCES;
    const policy = { ...DEFAULT_POLICY, ...(mirror?.policy ?? {}) };
    applyToDocument(resolve(preferences, policy, BUILTIN_THEMES), preferences);
  } catch {
    // keep the CSS defaults
  }
}
