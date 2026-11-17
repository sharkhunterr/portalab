/**
 * Issue 483: the chart series' colours, told apart whatever the palette. A palette's two accents are a
 * harmonious pair (amber: #ffd43b and #fcc419) — fine for the interface, unreadable as two series (films and
 * series the same yellow). The first series keeps the accent; the next nine are picked from a pool of hues,
 * each the farthest (OKLab) from the accent and from those already picked.
 */

/**
 * twelve hues (every 30° of OKLCH) at two lightnesses, readable on dark surfaces (L 0.68 and 0.80), then on
 * light ones (L 0.48 and 0.60, for their contrast on white)
 */
const POOL: Record<"dark" | "light", string[]> = {
  dark: [
    "#e06c94",
    "#e6705f",
    "#da7e1e",
    "#b79420",
    "#8da523",
    "#45b164",
    "#16b09b",
    "#25aabe",
    "#1aa2eb",
    "#7591f4",
    "#a780e6",
    "#cb73c4",
    "#fd9cba",
    "#fda293",
    "#ffa659",
    "#e3b831",
    "#b2cb52",
    "#6ed889",
    "#23dbc1",
    "#2fd4ec",
    "#78c7fd",
    "#a4bbff",
    "#c8aefa",
    "#f398eb",
  ],
  light: [
    "#9c2e5a",
    "#a13124",
    "#894c06",
    "#715b13",
    "#566609",
    "#067132",
    "#176c5f",
    "#0c6a76",
    "#006495",
    "#3e54b1",
    "#6c44a4",
    "#8a3785",
    "#c5547c",
    "#ca5747",
    "#bb6802",
    "#9c7c0b",
    "#768b09",
    "#25984d",
    "#239382",
    "#1590a1",
    "#1a89c5",
    "#5e78d9",
    "#8f68cb",
    "#b05baa",
  ],
};
export const SERIES_COUNT = 10;

function oklab(hex: string): [number, number, number] | null {
  const match = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim());
  if (!match?.[1]) return null;
  const digits = match[1].length === 3 ? [...match[1]].map((c) => c + c).join("") : match[1];
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = Number.parseInt(digits.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

/** OKLab distance × 100 between two hex colours (``Infinity`` when one is not a hex colour) */
export function colourDistance(a: string, b: string): number {
  const x = oklab(a);
  const y = oklab(b);
  if (!x || !y) return Number.POSITIVE_INFINITY;
  return 100 * Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}

/**
 * The ten series colours for an accent, on a dark or light theme: the accent first, then each time the hue
 * of the pool farthest from those already picked (the first pool's on a tie) — films and series far apart,
 * the first six well apart, all ten distinct.
 */
export function chartSeries(accent: string, scheme: "dark" | "light"): string[] {
  const picked = [accent];
  const left = [...POOL[scheme]];
  while (picked.length < SERIES_COUNT && left.length) {
    let best = 0;
    let bestApart = -1;
    for (const [index, colour] of left.entries()) {
      const apart = Math.min(...picked.map((other) => colourDistance(colour, other)));
      if (apart > bestApart) {
        best = index;
        bestApart = apart;
      }
    }
    picked.push(...left.splice(best, 1));
  }
  return picked;
}
