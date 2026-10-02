import { z } from "zod";
import { isColor } from "./contrast";

/**
 * ``ThemeDefinition`` (spec 022 R2/R3): a **closed**, declarative document. Themes are inert data: colors,
 * typography, radii, motion, icons, backgrounds (bundled assets or raster data URIs only), sounds (bundled
 * assets) and notification defaults — no scripts, no CSS, no external URLs, no unknown keys. Every one of
 * the ten functional states must be mapped; a theme changes how a state looks, never which states exist.
 */

export const FUNCTIONAL_STATES = [
  "loading",
  "available",
  "partial",
  "stale",
  "error",
  "unavailable",
  "maintenance",
  "unauthorized",
  "no-data",
  "syncing",
] as const;
export type FunctionalStateName = (typeof FUNCTIONAL_STATES)[number];
export const CRITICAL_STATES: readonly FunctionalStateName[] = [
  "error",
  "unauthorized",
  "maintenance",
  "unavailable",
];
export const ICON_IDS = [
  "spinner",
  "check",
  "half",
  "clock",
  "warning",
  "blocked",
  "wrench",
  "lock",
  "lines",
  "sync",
] as const;

export const THEME_SCHEMA_VERSION = 1;

const color = z.string().max(64).refine(isColor, { message: "expected a #hex or rgb()/rgba() color" });
const asset = z.string().regex(/^asset:[a-z0-9][a-z0-9._/-]{0,127}$/, "expected a bundled asset reference");
const rasterDataUri = z
  .string()
  .max(200_000)
  .regex(/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/, "only raster data URIs are allowed");
const labelKey = z.string().regex(/^[a-z][a-zA-Z0-9_.-]{0,127}$/);
const fontFamily = z
  .string()
  .max(200)
  .regex(/^[A-Za-z0-9 ,"'-]+$/, "font family names only");

const stateStyle = z.strictObject({
  fg: color,
  bg: color,
  icon: z.enum(ICON_IDS).optional(),
  label: labelKey.optional(),
  opacity: z.number().min(0).max(1).optional(),
  display: z.enum(["inline", "block", "none"]).optional(),
});

export const themeDefinitionSchema = z.strictObject({
  schemaVersion: z.literal(THEME_SCHEMA_VERSION),
  key: z.string().regex(/^[a-z][a-z0-9-]{1,47}$/),
  name: z.string().min(1).max(80),
  colorScheme: z.enum(["light", "dark"]),
  colors: z.strictObject({
    surface: color,
    surfaceRaised: color,
    text: color,
    textMuted: color,
    border: color,
    accent: color,
    accentContrast: color,
    focus: color,
  }),
  states: z.strictObject(
    Object.fromEntries(FUNCTIONAL_STATES.map((state) => [state, stateStyle])) as Record<
      FunctionalStateName,
      typeof stateStyle
    >,
  ),
  typography: z
    .strictObject({
      fontFamily: fontFamily.optional(),
      scale: z
        .strictObject({
          sm: z.number().min(0.75).max(1.25),
          md: z.number().min(0.875).max(1.5),
          lg: z.number().max(2.5),
          xl: z.number().max(3.5),
        })
        .optional(),
    })
    .optional(),
  radii: z.strictObject({ sm: z.number().min(0).max(2), md: z.number().min(0).max(3) }).optional(),
  motion: z
    .strictObject({ fastMs: z.number().int().min(0).max(1000), normalMs: z.number().int().min(0).max(2000) })
    .optional(),
  icons: z.strictObject({ set: z.enum(["default", "outline"]) }).optional(),
  background: z
    .strictObject({ image: z.union([asset, rasterDataUri]).optional(), fallback: color })
    .optional(),
  sounds: z.record(z.enum(["notification", "alert", "success"]), asset).optional(),
  notification: z
    .strictObject({
      position: z.enum(["top-end", "top-start", "bottom-end", "bottom-start"]).optional(),
      durationSeconds: z.number().int().min(2).max(60).optional(),
      style: z.enum(["toast", "banner"]).optional(),
    })
    .optional(),
});

export type ThemeDefinition = z.infer<typeof themeDefinitionSchema>;

export function parseTheme(value: unknown): { theme?: ThemeDefinition; errors: string[] } {
  const result = themeDefinitionSchema.safeParse(value);
  if (result.success) {
    return { theme: result.data, errors: [] };
  }
  return {
    errors: result.error.issues.map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`),
  };
}

/** JSON Schema of the theme document, shared with the backend registry (``modules/ui``). */
export function themeJsonSchema(): unknown {
  return z.toJSONSchema(themeDefinitionSchema);
}
