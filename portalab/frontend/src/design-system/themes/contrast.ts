/**
 * WCAG 2.2 contrast (spec 022 R4): relative luminance and contrast ratio of sRGB colors, with alpha
 * compositing over the background. Thresholds: 4.5:1 for normal text, 3:1 for large text and UI parts.
 */

export const TEXT_MIN = 4.5;
export const LARGE_OR_UI_MIN = 3;

export interface Rgba {
  r: number;
  g: number;
  b: number;
  a: number;
}

const HEX = /^#([0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
const RGB = /^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*(0|1|0?\.\d+))?\s*\)$/i;

export function isColor(value: string): boolean {
  return HEX.test(value) || RGB.test(value);
}

export function parseColor(value: string): Rgba {
  const hex = HEX.exec(value);
  if (hex) {
    let digits = hex[1] ?? "000";
    if (digits.length <= 4) {
      digits = [...digits].map((d) => d + d).join("");
    }
    const n = (i: number) => Number.parseInt(digits.slice(i, i + 2), 16);
    return { r: n(0), g: n(2), b: n(4), a: digits.length === 8 ? n(6) / 255 : 1 };
  }
  const rgb = RGB.exec(value);
  if (rgb) {
    const channel = (s: string) => Math.min(255, Number(s));
    return {
      r: channel(rgb[1] ?? "0"),
      g: channel(rgb[2] ?? "0"),
      b: channel(rgb[3] ?? "0"),
      a: rgb[4] === undefined ? 1 : Number(rgb[4]),
    };
  }
  throw new Error(`not a color: ${value}`);
}

/** Composite a (possibly translucent) color over an opaque background. */
export function over(top: Rgba, below: Rgba): Rgba {
  const a = top.a;
  return {
    r: top.r * a + below.r * (1 - a),
    g: top.g * a + below.g * (1 - a),
    b: top.b * a + below.b * (1 - a),
    a: 1,
  };
}

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function luminance(color: Rgba): number {
  return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
}

/** Contrast ratio between a foreground and a background (the background is composited over ``base``). */
export function contrast(foreground: string, background: string, base = "#ffffff"): number {
  const bg = over(parseColor(background), parseColor(base));
  const fg = over(parseColor(foreground), bg);
  const a = luminance(fg);
  const b = luminance(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
