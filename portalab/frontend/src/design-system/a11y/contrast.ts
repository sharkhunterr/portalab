import { HIGH_CONTRAST_KEY } from "../themes/builtin";
import type { UiPreferences } from "./preferences";

/** High contrast is an accessibility preference: it overrides the chosen theme (FR-011). */
export function themeKeyFor(preferences: UiPreferences, chosen: string): string {
  return preferences.contrast === "high" ? HIGH_CONTRAST_KEY : chosen;
}
