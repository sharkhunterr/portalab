/**
 * UI preferences (spec 022 data model): user-tier ``ui.*`` settings stored by Administration (020) and
 * mirrored to localStorage for first paint. Policy (allowed themes, text-scale bounds, forced reduced
 * motion) constrains the *effective* value while the stored preference is retained (CD-011).
 */

export type Density = "compact" | "comfortable" | "spacious";
export type ReducedMotion = "system" | "on" | "off";

export interface UiPreferences {
  theme: string | null;
  density: Density;
  textScale: number;
  contrast: "default" | "high";
  reducedMotion: ReducedMotion;
  soundEnabled: boolean;
  notificationPosition: "top-end" | "top-start" | "bottom-end" | "bottom-start";
  notificationDurationSeconds: number;
  notificationStyle: "toast" | "banner";
  campaignThemes: "allow" | "ignore";
  /** Light/dark choice for theme families (027 R8): dark by default, or follow the device. */
  colorMode: "dark" | "light" | "system";
}

export interface UiPolicy {
  allowedThemes: string[];
  defaultTheme: string;
  textScaleMin: number;
  textScaleMax: number;
  forceReducedMotion: boolean;
}

export const DEFAULT_PREFERENCES: UiPreferences = {
  theme: null,
  density: "comfortable",
  textScale: 1,
  contrast: "default",
  reducedMotion: "system",
  soundEnabled: true,
  notificationPosition: "top-end",
  notificationDurationSeconds: 6,
  notificationStyle: "toast",
  campaignThemes: "allow",
  colorMode: "dark",
};

export const DEFAULT_POLICY: UiPolicy = {
  allowedThemes: ["portalab-dark", "portalab-light", "light", "dark", "high-contrast"],
  defaultTheme: "portalab",
  textScaleMin: 0.85,
  textScaleMax: 2,
  forceReducedMotion: false,
};

/** ``ui.<name>`` setting keys of each preference field (declared by the backend ``ui`` module). */
export const PREFERENCE_KEYS: Record<keyof UiPreferences, string> = {
  theme: "ui.theme",
  density: "ui.density",
  textScale: "ui.textScale",
  contrast: "ui.contrast",
  reducedMotion: "ui.reducedMotion",
  soundEnabled: "ui.soundEnabled",
  notificationPosition: "ui.notificationPosition",
  notificationDurationSeconds: "ui.notificationDurationSeconds",
  notificationStyle: "ui.notificationStyle",
  campaignThemes: "ui.campaignThemes",
  colorMode: "ui.colorMode",
};

/** Accept only known fields with valid values (an option removed by an update falls back to its default). */
export function sanitize(input: object): UiPreferences {
  const raw = input as Record<string, unknown>;
  const out: UiPreferences = { ...DEFAULT_PREFERENCES };
  const pick = <K extends keyof UiPreferences>(key: K, allowed: readonly unknown[]) => {
    if (allowed.includes(raw[key])) {
      out[key] = raw[key] as UiPreferences[K];
    }
  };
  if (typeof raw.theme === "string" || raw.theme === null) out.theme = raw.theme ?? null;
  pick("density", ["compact", "comfortable", "spacious"]);
  pick("contrast", ["default", "high"]);
  pick("reducedMotion", ["system", "on", "off"]);
  pick("notificationPosition", ["top-end", "top-start", "bottom-end", "bottom-start"]);
  pick("notificationStyle", ["toast", "banner"]);
  pick("campaignThemes", ["allow", "ignore"]);
  pick("colorMode", ["dark", "light", "system"]);
  if (typeof raw.soundEnabled === "boolean") out.soundEnabled = raw.soundEnabled;
  if (typeof raw.textScale === "number" && Number.isFinite(raw.textScale)) out.textScale = raw.textScale;
  if (typeof raw.notificationDurationSeconds === "number") {
    out.notificationDurationSeconds = Math.min(60, Math.max(2, Math.round(raw.notificationDurationSeconds)));
  }
  return out;
}
