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
  // 027: more accents — each a pair no other palette has
  polar: {
    dark: { accent: "#88c0d0", accentAlt: "#a3be8c", contrast: "#10151c" },
    light: { accent: "#2e6a85", accentAlt: "#4f6b35", contrast: "#ffffff" },
  },
  copper: {
    dark: { accent: "#e8956a", accentAlt: "#5cc4b8", contrast: "#1e0d04" },
    light: { accent: "#a4471a", accentAlt: "#0f6b62", contrast: "#ffffff" },
  },
  solar: {
    dark: { accent: "#2fc4b5", accentAlt: "#f0b445", contrast: "#03201d" },
    light: { accent: "#0f6f66", accentAlt: "#8a5a00", contrast: "#ffffff" },
  },
  berry: {
    dark: { accent: "#f06aa8", accentAlt: "#9b7bff", contrast: "#24051a" },
    light: { accent: "#b0215f", accentAlt: "#5b3fd1", contrast: "#ffffff" },
  },
  slate: {
    dark: { accent: "#9db2d0", accentAlt: "#d2bd98", contrast: "#0e131b" },
    light: { accent: "#3f5576", accentAlt: "#6d5a3a", contrast: "#ffffff" },
  },
  peach: {
    dark: { accent: "#ffb199", accentAlt: "#9fd6f0", contrast: "#2a0f06" },
    light: { accent: "#a8452a", accentAlt: "#0d628a", contrast: "#ffffff" },
  },
  hawkins: {
    dark: { accent: "#ff3b4f", accentAlt: "#4fa3ff", contrast: "#1a0206" },
    light: { accent: "#b3122a", accentAlt: "#1d4ed8", contrast: "#ffffff" },
  },
  gondor: {
    dark: { accent: "#dbe4ee", accentAlt: "#d4af37", contrast: "#10151c" },
    light: { accent: "#334155", accentAlt: "#8a6d0b", contrast: "#ffffff" },
  },
  vhs: {
    dark: { accent: "#ffd23f", accentAlt: "#00d1ff", contrast: "#141000" },
    light: { accent: "#1d2bd6", accentAlt: "#a16207", contrast: "#ffffff" },
  },
  nostromo: {
    dark: { accent: "#e8c234", accentAlt: "#3de88a", contrast: "#05080c" },
    light: { accent: "#8a6d0b", accentAlt: "#15803d", contrast: "#ffffff" },
  },
  nova: {
    dark: { accent: "#8b7bff", accentAlt: "#22d3ee", contrast: "#0b0820" },
    light: { accent: "#5b3df5", accentAlt: "#0e7490", contrast: "#ffffff" },
  },
  crimson: {
    dark: { accent: "#ff5c6c", accentAlt: "#c7d0dc", contrast: "#24040a" },
    light: { accent: "#b3122a", accentAlt: "#4b5563", contrast: "#ffffff" },
  },
  // #81: the seasons
  pumpkinspice: {
    dark: { accent: "#ff9f43", accentAlt: "#d4a373", contrast: "#1f0e00" },
    light: { accent: "#b45309", accentAlt: "#7c4a1e", contrast: "#ffffff" },
  },
  evergreen: {
    dark: { accent: "#3ddc84", accentAlt: "#ff6b6b", contrast: "#03170b" },
    light: { accent: "#166534", accentAlt: "#b91c1c", contrast: "#ffffff" },
  },
  cherry: {
    dark: { accent: "#ff6f91", accentAlt: "#ffb3c6", contrast: "#26030d" },
    light: { accent: "#be123c", accentAlt: "#9d174d", contrast: "#ffffff" },
  },
  pastel: {
    dark: { accent: "#c4b5fd", accentAlt: "#99f6e4", contrast: "#1a1033" },
    light: { accent: "#6d28d9", accentAlt: "#0f766e", contrast: "#ffffff" },
  },
  tropical: {
    dark: { accent: "#2dd4bf", accentAlt: "#fb7185", contrast: "#03201c" },
    light: { accent: "#0f766e", accentAlt: "#be123c", contrast: "#ffffff" },
  },
  // #89: the universes
  scarletgold: {
    dark: { accent: "#f5c542", accentAlt: "#f87171", contrast: "#2a1a00" },
    light: { accent: "#991b1b", accentAlt: "#92400e", contrast: "#ffffff" },
  },
  rum: {
    dark: { accent: "#f0b84a", accentAlt: "#5eead4", contrast: "#241500" },
    light: { accent: "#92400e", accentAlt: "#115e59", contrast: "#ffffff" },
  },
  gunmetal: {
    dark: { accent: "#f87171", accentAlt: "#cbd5e1", contrast: "#2a0606" },
    light: { accent: "#b91c1c", accentAlt: "#374151", contrast: "#ffffff" },
  },
  // #89: the desktop, the fruit company, the social network
  luna: {
    dark: { accent: "#6ea8ff", accentAlt: "#7fd36b", contrast: "#04122e" },
    light: { accent: "#1f55c8", accentAlt: "#2c7a1f", contrast: "#ffffff" },
  },
  graphite: {
    dark: { accent: "#d1d5db", accentAlt: "#7dd3fc", contrast: "#111827" },
    light: { accent: "#3a3a3c", accentAlt: "#0066cc", contrast: "#ffffff" },
  },
  chatgradient: {
    dark: { accent: "#7aa7ff", accentAlt: "#f472b6", contrast: "#07122a" },
    light: { accent: "#1660c9", accentAlt: "#b0237a", contrast: "#ffffff" },
  },
};

export function paletteFor(key: string, scheme: "dark" | "light"): Palette | null {
  return PALETTE_COLORS[key]?.[scheme] ?? null;
}
