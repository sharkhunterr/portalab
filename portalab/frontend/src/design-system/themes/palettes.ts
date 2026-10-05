/**
 * Colour palettes (027): accent colours laid over any theme — the theme keeps its surfaces, text and
 * layout; a palette only changes the accents (and their readable contrast colour). Some are sold in the
 * shop. Never applied in high contrast (the accessibility theme keeps its own colours).
 */
export interface Palette {
  accent: string;
  accentAlt: string;
  contrast: string;
}

export const PALETTE_COLORS: Record<string, { dark: Palette; light: Palette }> = {
  ocean: {
    dark: { accent: "#38bdf8", accentAlt: "#2dd4bf", contrast: "#04121c" },
    light: { accent: "#0369a1", accentAlt: "#0f766e", contrast: "#ffffff" },
  },
  forest: {
    dark: { accent: "#4ade80", accentAlt: "#a3e635", contrast: "#05170b" },
    light: { accent: "#15803d", accentAlt: "#4d7c0f", contrast: "#ffffff" },
  },
  sunset: {
    dark: { accent: "#fb923c", accentAlt: "#f472b6", contrast: "#1c0a02" },
    light: { accent: "#c2410c", accentAlt: "#be185d", contrast: "#ffffff" },
  },
  candy: {
    dark: { accent: "#f9a8d4", accentAlt: "#6ee7b7", contrast: "#1f0614" },
    light: { accent: "#be185d", accentAlt: "#047857", contrast: "#ffffff" },
  },
  royal: {
    dark: { accent: "#a78bfa", accentAlt: "#fbbf24", contrast: "#0f0720" },
    light: { accent: "#6d28d9", accentAlt: "#b45309", contrast: "#ffffff" },
  },
  ember: {
    dark: { accent: "#f87171", accentAlt: "#fbbf24", contrast: "#1c0505" },
    light: { accent: "#b91c1c", accentAlt: "#b45309", contrast: "#ffffff" },
  },
  matrix: {
    dark: { accent: "#22c55e", accentAlt: "#86efac", contrast: "#021006" },
    light: { accent: "#15803d", accentAlt: "#166534", contrast: "#ffffff" },
  },
};

export function paletteFor(key: string, scheme: "dark" | "light"): Palette | null {
  return PALETTE_COLORS[key]?.[scheme] ?? null;
}
