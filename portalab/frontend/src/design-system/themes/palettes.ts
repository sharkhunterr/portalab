/**
 * Colour palettes (027): accent colours laid over any theme — the theme keeps its surfaces, text and
 * layout; a palette only changes the accents (and their readable contrast colour). Some are sold in the
 * shop. Never applied in high contrast (the accessibility theme keeps its own colours).
 */
import { externalPalette } from "../visuals/registry";

export interface Palette {
  accent: string;
  accentAlt: string;
  contrast: string;
}

/** 028: the socle's palettes, drawn before any pack is read (first paint) — every other palette's colours are
 * its pack's (``externalPalette``), none is listed here. */
export const PALETTE_COLORS: Record<string, { dark: Palette; light: Palette }> = {
  ocean: {
    dark: { accent: "#38bdf8", accentAlt: "#2dd4bf", contrast: "#04121c" },
    light: { accent: "#0369a1", accentAlt: "#0f766e", contrast: "#ffffff" },
  },
  forest: {
    dark: { accent: "#4ade80", accentAlt: "#a3e635", contrast: "#05170b" },
    light: { accent: "#15803d", accentAlt: "#4d7c0f", contrast: "#ffffff" },
  },
};

export function paletteFor(key: string, scheme: "dark" | "light"): Palette | null {
  const builtin = PALETTE_COLORS[key]?.[scheme];
  if (builtin) return builtin;
  const external = externalPalette(key, scheme); // 028: a pack's palette
  return external ? { ...external, contrast: external.contrast ?? "#ffffff" } : null;
}
