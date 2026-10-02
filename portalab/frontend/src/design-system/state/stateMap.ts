import { FUNCTIONAL_STATES, type FunctionalStateName, type ICON_IDS } from "../themes/schema";

/**
 * Standardized functional states (CD-022, spec 022 R3): a closed set with fixed meaning. Themes change how a
 * state looks (color, icon, label wording), never the set itself, its meaning or its accessible name.
 */
export { FUNCTIONAL_STATES, type FunctionalStateName };

export type IconId = (typeof ICON_IDS)[number];

/** Default English labels — replaced by i18n catalogs (spec 026). The meaning never changes per theme. */
export const STATE_LABELS: Record<FunctionalStateName, string> = {
  loading: "Loading",
  available: "Available",
  partial: "Partially available",
  stale: "Out of date",
  error: "Error",
  unavailable: "Unavailable",
  maintenance: "Under maintenance",
  unauthorized: "Not allowed",
  "no-data": "No data yet",
  syncing: "Syncing",
};

export const DEFAULT_ICONS: Record<FunctionalStateName, IconId> = {
  loading: "spinner",
  available: "check",
  partial: "half",
  stale: "clock",
  error: "warning",
  unavailable: "blocked",
  maintenance: "wrench",
  unauthorized: "lock",
  "no-data": "lines",
  syncing: "sync",
};

export const ICON_PATHS: Record<IconId, string> = {
  spinner: "M12 3a9 9 0 1 0 9 9h-2a7 7 0 1 1-7-7z",
  check: "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z",
  half: "M12 2a10 10 0 1 0 0 20V2z",
  clock: "M12 7v5l4 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  warning: "M12 2 1 21h22zm0 6v6m0 3v.01",
  blocked: "M4 4l16 16M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  wrench: "M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.1-2.1z",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5z",
  lines: "M4 6h16M4 12h16M4 18h10",
  sync: "M4 12a8 8 0 0 1 14-5.3L20 9M20 12a8 8 0 0 1-14 5.3L4 15",
};

export function isFunctionalState(value: string): value is FunctionalStateName {
  return (FUNCTIONAL_STATES as readonly string[]).includes(value);
}
