import type { CSSProperties } from "react";
import { Icon } from "../../design-system/components/Icon";

/**
 * Generated article covers (027 T095): articles carry no image, so each one gets a stable gradient derived
 * from its category (or slug) — the theme accents, hue-rotated by a stable amount, so the same category
 * always has the same colors in a given theme.
 * Decorative only: the title is always the accessible name.
 */
export function hueOf(seed: string): number {
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) % 360;
  return hash;
}

export function coverStyle(seed: string): CSSProperties {
  const hue = hueOf(seed);
  return { "--cover-hue": String(hue), "--cover-mix": String(30 + (hue % 50)) } as CSSProperties;
}

export function Cover({ seed, label, size = "md" }: { seed: string; label?: string; size?: "md" | "lg" }) {
  return (
    <span className="news-cover" data-size={size} style={coverStyle(seed)} aria-hidden="true">
      <Icon name="newspaper" size={size === "lg" ? 44 : 28} />
      {label ? <span className="news-cover__label">{label}</span> : null}
    </span>
  );
}

/** Reading time from the text length (≈ 200 words a minute, at least one). */
export function readingMinutes(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 200));
}
