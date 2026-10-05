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
  aurora: {
    dark: { accent: "#5eead4", accentAlt: "#a78bfa", contrast: "#04121a" },
    light: { accent: "#0f766e", accentAlt: "#6d28d9", contrast: "#ffffff" },
  },
  lagoon: {
    dark: { accent: "#22d3ee", accentAlt: "#34d399", contrast: "#03141a" },
    light: { accent: "#0e7490", accentAlt: "#047857", contrast: "#ffffff" },
  },
  lava: {
    dark: { accent: "#ff6b35", accentAlt: "#ffd23f", contrast: "#1c0700" },
    light: { accent: "#c2410c", accentAlt: "#a16207", contrast: "#ffffff" },
  },
  mint: {
    dark: { accent: "#6ee7b7", accentAlt: "#a7f3d0", contrast: "#04170f" },
    light: { accent: "#047857", accentAlt: "#0f766e", contrast: "#ffffff" },
  },
  gold: {
    dark: { accent: "#fbbf24", accentAlt: "#fde68a", contrast: "#1c1300" },
    light: { accent: "#a16207", accentAlt: "#92400e", contrast: "#ffffff" },
  },
  ice: {
    dark: { accent: "#7dd3fc", accentAlt: "#e0f2fe", contrast: "#04121c" },
    light: { accent: "#0369a1", accentAlt: "#0e7490", contrast: "#ffffff" },
  },
  rose: {
    dark: { accent: "#fb7185", accentAlt: "#fda4af", contrast: "#1f0509" },
    light: { accent: "#be123c", accentAlt: "#9f1239", contrast: "#ffffff" },
  },
  toxic: {
    dark: { accent: "#a3e635", accentAlt: "#facc15", contrast: "#0f1702" },
    light: { accent: "#4d7c0f", accentAlt: "#a16207", contrast: "#ffffff" },
  },
  midnight: {
    dark: { accent: "#818cf8", accentAlt: "#38bdf8", contrast: "#070a1f" },
    light: { accent: "#4338ca", accentAlt: "#0369a1", contrast: "#ffffff" },
  },
  coffee: {
    dark: { accent: "#d6a77a", accentAlt: "#f2d0a4", contrast: "#1a0f06" },
    light: { accent: "#8a4b2d", accentAlt: "#7c4a1e", contrast: "#ffffff" },
  },
  lavender: {
    dark: { accent: "#c4b5fd", accentAlt: "#f0abfc", contrast: "#120a24" },
    light: { accent: "#6d28d9", accentAlt: "#a21caf", contrast: "#ffffff" },
  },
  bubblegum: {
    dark: { accent: "#f9a8d4", accentAlt: "#7dd3fc", contrast: "#1f0614" },
    light: { accent: "#be185d", accentAlt: "#0369a1", contrast: "#ffffff" },
  },
};

export function paletteFor(key: string, scheme: "dark" | "light"): Palette | null {
  return PALETTE_COLORS[key]?.[scheme] ?? null;
}
