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
  // issue 455: ten more offered to everyone (WCAG AA: their text on the accent, the accent on white)
  tangerine: {
    dark: { accent: "#ffa94d", accentAlt: "#f783ac", contrast: "#1c0a02" },
    light: { accent: "#b8460c", accentAlt: "#a8245e", contrast: "#ffffff" },
  },
  wisteria: {
    dark: { accent: "#d0bfff", accentAlt: "#b197fc", contrast: "#140b2e" },
    light: { accent: "#6236c4", accentAlt: "#7a3fd1", contrast: "#ffffff" },
  },
  ruby: {
    dark: { accent: "#ff7a7a", accentAlt: "#f06595", contrast: "#1f0509" },
    light: { accent: "#b3143c", accentAlt: "#8f1336", contrast: "#ffffff" },
  },
  amber: {
    dark: { accent: "#ffd43b", accentAlt: "#fcc419", contrast: "#1c1002" },
    light: { accent: "#a65a07", accentAlt: "#8a4a0b", contrast: "#ffffff" },
  },
  seafoam: {
    dark: { accent: "#63e6be", accentAlt: "#66d9e8", contrast: "#03140e" },
    light: { accent: "#0b7a5c", accentAlt: "#0e6f73", contrast: "#ffffff" },
  },
  sky: {
    dark: { accent: "#74c0fc", accentAlt: "#91a7ff", contrast: "#04121c" },
    light: { accent: "#1e54d1", accentAlt: "#4a3fc4", contrast: "#ffffff" },
  },
  petal: {
    dark: { accent: "#fcc2d7", accentAlt: "#e599f7", contrast: "#24071a" },
    light: { accent: "#b0195a", accentAlt: "#9b1ea8", contrast: "#ffffff" },
  },
  coral: {
    dark: { accent: "#ffa8a8", accentAlt: "#fdba74", contrast: "#240a0d" },
    light: { accent: "#b42318", accentAlt: "#b9461a", contrast: "#ffffff" },
  },
  stone: {
    dark: { accent: "#c9d2de", accentAlt: "#94a3b8", contrast: "#0f172a" },
    light: { accent: "#3a4556", accentAlt: "#4e5a6a", contrast: "#ffffff" },
  },
  opal: {
    dark: { accent: "#38d9a9", accentAlt: "#da77f2", contrast: "#031a17" },
    light: { accent: "#0d7268", accentAlt: "#7424b8", contrast: "#ffffff" },
  },
};

export function paletteFor(key: string, scheme: "dark" | "light"): Palette | null {
  const builtin = PALETTE_COLORS[key]?.[scheme];
  if (builtin) return builtin;
  const external = externalPalette(key, scheme); // 028: a pack's palette
  return external ? { ...external, contrast: external.contrast ?? "#ffffff" } : null;
}
